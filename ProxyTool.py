# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Author: Florent Guillaume <fg@nuxeo.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$
"""Proxy Tool that manages proxy objects and their links to real documents.
"""

from zLOG import LOG, ERROR, DEBUG
from Globals import InitializeClass, DTMLFile
from Globals import PersistentMapping
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from AccessControl.PermissionRole import rolesForPermissionOn

from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation

from Products.NuxUserGroups.CatalogToolWithGroups import mergedLocalRoles
from Products.NuxCPS3.ProxyBase import ProxyBase
from Products.NuxCPS3.EventServiceTool import getEventService


class ProxyTool(UniqueObject, SimpleItemWithProperties):
    """A proxy tool manages relationships between proxy objects
    and the documents they point to.

    The proxy tool must be registered with the event service to receive
    sys_add_object and sys_del_object events, with action 'proxy'.
    """

    id = 'portal_proxies'
    meta_type = 'CPS Proxies Tool'

    security = ClassSecurityInfo()

    def __init__(self):
        self._hubid_to_info = PersistentMapping()

    #
    # External API
    #

    security.declarePrivate('createProxy')
    def createProxy(self, proxy_type, container, type_name, id, *args, **kw):
        """Create a new proxy to a new document.

        Returns the created proxy object.
        Does not insert the proxy into any workflow.
        proxy_type is one of 'folder', 'document' or 'folderishdocument'.
        """
        LOG('createProxy', DEBUG, 'Called with proxy_type=%s container=%s '
            'type_name=%s id=%s' % (proxy_type, container.getId(),
                                    type_name, id))
        if proxy_type == 'folder':
            proxy_type_name = 'CPS Proxy Folder'
        elif proxy_type == 'folderishdocument':
            proxy_type_name = 'CPS Proxy Folderish Document'
        else:
            proxy_type_name = 'CPS Proxy Document'
        # Create the document in the repository
        repotool = getToolByName(self, 'portal_repository')
        repoid, version_info = repotool.invokeFactory(type_name, repoid=None,
                                                      version_info=None,
                                                      *args, **kw)
        version_infos = {'*': version_info}
        # Create the proxy to that document
        # The proxy is a normal CMF object except that we change its
        # portal_type after construction.
        ob = self.constructContent(container, # XXX
                                   proxy_type_name, id,
                                   final_type_name=type_name,
                                   repoid=repoid,
                                   version_infos=version_infos)
        return ob

    security.declarePrivate('listProxies')
    def listProxies(self):
        """List all proxies.

        Returns a sequence of (hubid, (repoid, version_infos)).
        NOTE that the version_infos mapping should not be mutated!
        """
        all = self._hubid_to_info.items()
        all.sort() # Sort by hubid.
        return all

    security.declarePrivate('getContent')
    def getContent(self, hubid, lang=None, editable=0):
        # XXX should this take a hubid or a proxy as argument?
        """Get the object best matched by a given proxy.

        If lang is not passed, takes into account the user language.
        Returns an object, and the lang and version used. XXX
        Returns None, None, None if there is no match.

        If editable, the returned content must be an unfrozen version,
        so a cloning and a version upgrade may happen behind the scene.

        (Called by ProxyBase.)
        """
        repotool = getToolByName(self, 'portal_repository')
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Getting unknown hubid %s' % hubid)
            return None, None, None
        repoid, version_infos = self._hubid_to_info[hubid]
        if lang is None:
            # XXX get preferred language here - abstract the negociation
            # XXX use Localizer methods
            lang = '*'
        # Find version to use.
        if version_infos.has_key(lang):
            version_info = version_infos[lang]
        elif version_infos.has_key('*'):
            version_info = version_infos['*']
            lang = '*'
        else:
            LOG('ProxyTool', DEBUG, 'Found no matching version for hubid %s, repoid %s, lang %s, infos %s' % (hubid, repoid, lang, version_infos))
            return None, None, None
        if editable:
            LOG('ProxyTool', DEBUG, 'Wants editable instead of v=%s' %
                version_info)
            version_info = repotool.getUnfrozenVersion(repoid, version_info)
            LOG('ProxyTool', DEBUG, ' Got v=%s' % version_info)
            # Now update info
            version_infos[lang] = version_info
            self._hubid_to_info[hubid] = (repoid, version_infos)
        return repotool.getObjectVersion(repoid, version_info), lang, version_info

    security.declarePrivate('getMatchingProxies')
    def getMatchingProxies(self, repoid, version_info):
        """Get the proxies matching a given version of an object.

        Returns a mapping of {hubid: [list of lang]}
        """
        infos = {}
        # XXX must be made faster using a second mapping (repoid, vi) -> hubid
        for hubid, (rid, version_infos) in self._hubid_to_info.items():
            if repoid != rid:
                continue
            for lang, vi in version_infos.items():
                if version_info == vi:
                    infos.setdefault(hubid, []).append(lang)
        return infos

    security.declarePublic('getProxiesFromId')
    def getProxiesFromId(self, id):
        """Get the proxy infos from a repo id (gotten from the catalog).

        Only returns the proxies that are visible.
        """
        repotool = getToolByName(self, 'portal_repository')
        hubtool = getToolByName(self, 'portal_eventservice')
        portal = aq_parent(aq_inner(self))
        repoid, version_info = repotool.getRepoIdAndVersionFromId(id)
        if repoid is None:
            return []
        infos = self.getMatchingProxies(repoid, version_info)
        res = []
        for hubid, langs in infos.items():
            rpath = hubtool.getLocation(hubid, relative=1)
            ob = portal.unrestrictedTraverse(rpath)
            if _checkPermission(View, ob):
                res.append({'object': ob,
                            'rpath': rpath,
                            'hubid': hubid,
                            'langs': langs,
                            })
        return res

    security.declarePrivate('freezeProxy')
    def freezeProxy(self, hubid):
        """Freeze a proxy.

        (Called by ProxyBase.)
        """
        # XXX use an event?
        #LOG('ProxyTool', DEBUG, 'Freezeing hubid=%s' % hubid)
        if not self._hubid_to_info.has_key(hubid):
            #LOG('ProxyTool', ERROR, 'Getting unknown hubid %s' % hubid)
            raise ValueError(hubid)
        repoid, version_infos = self._hubid_to_info[hubid]
        repotool = getToolByName(self, 'portal_repository')
        for lang, version_info in version_infos.items():
            #LOG('ProxyTool', DEBUG, ' Freezeing repoid=%s v=%s'
            #    % (repoid, version_info))
            repotool.freezeVersion(repoid, version_info)

    security.declarePrivate('unshareContent')
    def unshareContent(self, hubid):
        """Unshare content (after a copy/paste for instance."""
        repotool = getToolByName(self, 'portal_repository')
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Getting unknown hubid %s' % hubid)
            return None
        repoid, version_infos = self._hubid_to_info[hubid]
        new_version_infos = {}
        for lang, vi in version_infos.items():
            new_vi = repotool.copyVersion(repoid, vi)
            new_version_infos[lang] = new_vi
        self._hubid_to_info[hubid] = (repoid, new_version_infos)

    security.declarePrivate('setSecurity')
    def setSecurity(self, ob):
        """Reapply the security info to the versions of a proxy.

        (Called by ProxyBase.) XXX but should use an event
        """
        # XXX should not get directly an object... or should it?
        #LOG('setSecurity', DEBUG, '--- ob %s' % '/'.join(ob.getPhysicalPath()))
        if not isinstance(ob, ProxyBase):
            return
        # XXX should be sent also by the one sending an event instead of
        #     calling this directly
        evtool = getEventService(self)
        evtool.notify('sys_modify_security', ob, {})

        hubtool = getToolByName(self, 'portal_eventservice')
        repotool = getToolByName(self, 'portal_repository')
        # Gather versions
        repoid = ob.getRepoId()
        version_infos = ob.getVersionInfos()
        versions = {}
        for lang, version_info in version_infos.items():
            versions[version_info] = None
        versions = versions.keys()
        #LOG('setSecurity', DEBUG, 'repoid %s versions %s' % (repoid, versions))
        # Gather the hubids of proxies pointing to any version
        hubids = {}
        for version_info in versions:
            # For each version, get all the proxies pointing to it
            infos = self.getMatchingProxies(repoid, version_info)
            for hubid in infos.keys():
                hubids[hubid] = None
        hubids = hubids.keys()
        #LOG('setSecurity', DEBUG, 'hubids %s' % (hubids,))
        # Get user permissions for users that have a (merged) local role
        allperms = self._getRelevantPermissions()
        #LOG('setSecurity', DEBUG, 'relevant perms %s' % (allperms,))
        userperms = {}
        portal = aq_parent(aq_inner(self))
        for hubid in hubids:
            location = hubtool.getLocation(hubid)
            #LOG('setSecurity', DEBUG, 'location %s' % (location,))
            if location is None:
                continue
            ob = portal.unrestrictedTraverse(location)
            merged = mergedLocalRoles(ob, withgroups=1).items()
            #LOG('setSecurity', DEBUG, 'merged %s' % (merged,))
            # Collect permissions of users
            for perm in allperms:
                proles = rolesForPermissionOn(perm, ob)
                #LOG('setSecurity', DEBUG, '  perm %s proles %s'
                #    % (perm, proles))
                for user, lroles in merged:
                    #LOG('setSecurity', DEBUG, '    user %s' % (user,))
                    for lr in lroles:
                        if lr in proles:
                            perms = userperms.setdefault(user, [])
                            if perm not in perms:
                                #LOG('setSecurity', DEBUG, '      addperm')
                                perms.append(perm)
        #LOG('setSecurity', DEBUG, 'userperms is %s' % (userperms,))
        # Now set security on versions.
        for version_info in versions:
            repotool.setObjectSecurity(repoid, version_info, userperms)
            ob = repotool.getObjectVersion(repoid, version_info)

    def _getRelevantPermissions(self):
        """Get permissions relevant to security info discovery."""
        # Get all the permissions managed by all the workflows.
        wftool = getToolByName(self, 'portal_workflow')
        return wftool.getManagedPermissions()

    #
    # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # This does object construction like TypesTool but without security
    # checks (which are already done by WorkflowTool).
    #

    def _constructInstance_fti(self, container, ti, id, *args, **kw):
        if not ti.product or not ti.factory:
            raise ValueError('Product factory for %s was undefined: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        p = container.manage_addProduct[ti.product]
        meth = getattr(p, ti.factory, None)
        if meth is None:
            raise ValueError('Product factory for %s was invalid: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        if getattr(aq_base(meth), 'isDocTemp', 0):
            newid = meth(meth.aq_parent, self.REQUEST, id=id, *args, **kw)
        else:
            newid = meth(id, *args, **kw)
        newid = newid or id
        return container._getOb(newid)

    def _constructInstance_sti(self, container, ti, id, *args, **kw):
        constr = container.restrictedTraverse(ti.constructor_path)
        constr = aq_base(constr).__of__(container)
        return constr(container, id, *args, **kw)

    security.declarePrivate('constructContent')
    def constructContent(self, container, type_name, id, final_type_name=None,
                         *args, **kw):
        """Construct an CMFish object without all the security checks.

        Do not insert into any workflow.

        Returns the object.
        """
        ttool = getToolByName(self, 'portal_types')
        ti = ttool.getTypeInfo(type_name)
        if ti is None:
            raise ValueError('No type information for %s' % type_name)
        if isinstance(ti, FactoryTypeInformation):
            ob = self._constructInstance_fti(container, ti, id, *args, **kw)
        elif isinstance(ti, ScriptableTypeInformation):
            ob = self._constructInstance_sti(container, ti, id, *args, **kw)
        else:
            raise ValueError('Unknown type information class for %s' %
                             type_name)
        if ob.getId() != id:
            # Sanity check
            raise ValueError('Constructing %s, id changed from %s to %s' %
                             (type_name, id, ob.getId()))
        if final_type_name is None:
            final_type_name = type_name
        ob._setPortalTypeName(final_type_name)
        ob.reindexObject(idxs=['portal_type', 'Type'])
        # XXX should notify something
        return ob

    #
    # Internal
    #

    security.declarePrivate('addProxy')
    def addProxy(self, hubid, repoid, version_infos):
        """Add knowledge about a new proxy.

        The hubid is the one of the proxy.
        The repoid is the document family pointed to.
        The version_infos mapping stores a correspondance between language
        and version. Language may be '*'. Version is an integer.
        """
        if self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR,
                'Adding already added hubid %s, repoid %s' % (hubid, repoid))
        self._hubid_to_info[hubid] = (repoid, version_infos)

    security.declarePrivate('delProxy')
    def delProxy(self, hubid):
        """Delete knowledge about a proxy."""
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Deleting unknown hubid %s' % hubid)
        else:
            del self._hubid_to_info[hubid]

    security.declarePrivate('modifyProxy')
    def modifyProxy(self, hubid, repoid, version_infos):
        """Modify knowledge about a proxy."""
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR,
                'Modifying unknown hubid %s, repoid %s' % (hubid, repoid))
        self.delProxy(hubid)
        self.addProxy(hubid, repoid, version_infos)

    #
    # Event notification
    #

    security.declarePrivate('notify_proxy')
    def notify_proxy(self, event_type, object, infos):
        """Notification from the event service.

        Called when a proxy is added/deleted. Updates the list
        of existing proxies.

        Called when a document is modified. Notifies the proxies
        that they have implicitly been modified.
        """
        if event_type in ('sys_add_object', 'sys_del_object'):
            if not isinstance(object, ProxyBase):
                return
            hubid = infos['hubid']
            if event_type == 'sys_add_object':
                repoid = object.getRepoId()
                version_infos = object.getVersionInfos()
                self.addProxy(hubid, repoid, version_infos)
            elif event_type == 'sys_del_object':
                self.delProxy(hubid)
            # Refresh security
            self.setSecurity(object)

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Proxies',
         'action': 'manage_listProxies',
        },
        ) + SimpleItemWithProperties.manage_options

    security.declareProtected(ViewManagementScreens, 'manage_listProxies')
    manage_listProxies = DTMLFile('zmi/proxy_list_proxies', globals())


InitializeClass(ProxyTool)
