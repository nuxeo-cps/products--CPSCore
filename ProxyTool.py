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
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from AccessControl.PermissionRole import rolesForPermissionOn
from BTrees.OOBTree import OOBTree

from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ManagePortal
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import mergedLocalRoles
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation

from Products.CPSCore.utils import _isinstance
from Products.CPSCore.ProxyBase import ProxyBase
from Products.CPSCore.EventServiceTool import getEventService


class ProxyTool(UniqueObject, SimpleItemWithProperties):
    """The proxy tool caches global informations about all proxies.

    The global information is used to find quickly all the proxies
    matching certain criteria:

    - rpath -> (docid, {lang: rev})

    - docid -> [rpaths]

    - docid, rev -> [rpaths]



    - also workflow state ?

    The proxy tool must be registered with the event service to receive
    sys_add_object and sys_del_object events, with action 'proxy'.
    """

    id = 'portal_proxies'
    meta_type = 'CPS Proxies Tool'

    security = ClassSecurityInfo()

    def __init__(self):
        self._clear()

    def _clear(self):
        self._rpath_to_infos = OOBTree()
        self._docid_rev_to_rpaths = OOBTree()
        self._docid_to_rpaths = OOBTree()

    #
    # External API
    #

    security.declarePrivate('createEmptyProxy')
    def createEmptyProxy(self, proxy_type, container, type_name, id,
                         docid=None):
        """Create an empty proxy.

        If docid is None, generate a new one.

        (Called by WorkflowTool.)
        """
        LOG('ProxyTool', DEBUG, "createEmptyProxy called with proxy_type=%s "
            "container=%s type_name=%s id=%s docid=%s"
            % (proxy_type, container.getId(), type_name, id, docid))
        proxy_type_name = {
            'folder':            'CPS Proxy Folder',
            'folderishdocument': 'CPS Proxy Folderish Document',
            }.get(proxy_type,    'CPS Proxy Document')
        if docid is None:
            repotool = getToolByName(self, 'portal_repository')
            docid = repotool.getFreeDocid()
        proxy = self.constructContent(container,
                                      proxy_type_name, id,
                                      final_type_name=type_name,
                                      docid=docid)
        return proxy


    security.declarePrivate('createRevision')
    def createRevision(self, proxy_, lang_, *args, **kw):
        """Create a language's revision for a proxy.

        Returns the revision.

        (Called by WorkflowTool.)
        """
        proxy = proxy_ # prevent name collision in **kw
        lang = lang_
        LOG('ProxyTool', DEBUG, "createRevision lang=%s for %s" %
            ('/'.join(proxy.getPhysicalPath()), lang))
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()
        type_name = proxy.getPortalTypeName()
        ob, rev = repotool.createRevision(docid, type_name, *args, **kw)
        if hasattr(aq_base(ob), 'setLanguage'):
            ob.setLanguage(lang)
            ob.reindexObject(idxs=['Language'])
        proxy.setLanguageRevision(lang, rev)
        proxy.proxyChanged()
        LOG('ProxyTool', DEBUG, "  created rev=%s" % rev)
        return rev




    security.declarePrivate('checkoutRevisions')
    def checkoutRevisions(self, proxy, new_proxy, language_map):
        """Checkout a proxy's revisions into a new proxy.

        Uses a language map to decide the language correspondances.

        All copied revisions are frozen.
        """
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()

        if language_map is None:
            # Keep same languages, simple checkout.
            for lang, rev in proxy._getLanguageRevisions().items():
                repotool.freezeRevision(docid, rev)
                new_proxy.setLanguageRevision(lang, rev)

        else:
            # Checkout with specific languages.
            for new_lang, lang in language_map.items():
                real_lang, rev = self.getBestRevision(proxy, lang)
                if new_lang == real_lang:
                    new_rev = rev
                    repotool.freezeRevision(docid, rev)
                else:
                    # Create a new revision, because the language changed.
                    new_ob, new_rev = repotool.copyRevision(docid, rev)
                    if hasattr(aq_base(new_ob), 'setLanguage'):
                        new_ob.setLanguage(new_lang)
                        # XXX reindex ?

                new_proxy.setLanguageRevision(new_lang, new_rev)

        new_proxy.proxyChanged()

    security.declarePrivate('checkinRevisions')
    def checkinRevisions(self, proxy, dest_proxy):
        """Checkin a proxy's revisions into a destination proxy.

        Also used for proxy merge.
        """
        if proxy.getDocid() != dest_proxy.getDocid():
            raise ValueError('Proxies have different docids.')
        for lang, rev in proxy._getLanguageRevisions().items():
            dest_proxy.setLanguageRevision(lang, rev)
        dest_proxy.proxyChanged()

    security.declarePrivate('listProxies')
    def listProxies(self):
        """List all proxies.

        Returns a sequence of (rpath, language_revs).
        NOTE that the version_infos mapping should not be mutated!
        """
        all = list(self._rpath_to_infos.items())
        all.sort() # Sort by rpath.
        return all

    security.declarePrivate('getBestRevision')
    def getBestRevision(self, proxy, lang=None):
        """Get the best language and revision for a proxy.

        Returns lang, rev.
        """
        if lang is None:
            # Find the user-preferred language.
            portal = getToolByName(self, 'portal_url').getPortalObject()
            if hasattr(portal, 'Localizer'):
                lang = portal.Localizer.get_selected_language()
            else:
                lang = 'en'
        default_language = proxy.getDefaultLanguage()
        language_revs = proxy._getLanguageRevisions()
        if language_revs.has_key(lang):
            # Ok.
            pass
        elif language_revs.has_key(default_language):
            # Default language is available.
            lang = default_language
        else:
            if not language_revs:
                # Proxy construction not finished.
                return None, None
            # Find the first available language.
            langs = language_revs.keys()
            langs.sort()
            lang = langs[0]
        return lang, language_revs[lang]

    security.declarePrivate('getContent')
    def getContent(self, proxy, lang=None, editable=0):
        """Get the object best matched by a given proxy.

        Returns the object.
        Raises KeyError if the language cannot be found.

        If lang is not passed, takes into account the user language.

        If editable, the returned content must be an unfrozen version,
        so a cloning and a version upgrade may happen behind the scene.

        (Called by ProxyBase.)
        """
        repotool = getToolByName(self, 'portal_repository')

        docid = proxy.getDocid()

        # Find version to use.
        lang, rev = self.getBestRevision(proxy, lang=lang)
        if lang is None:
            return None # Proxy not yet finished.

        if editable:
            newob, newrev = repotool.getUnfrozenRevision(docid, rev)

            LOG('ProxyTool', DEBUG,
                'getContent editable, rev=%s -> %s' % (rev, newrev))

            if newrev != rev:
                proxy.setLanguageRevision(lang, newrev)
                proxy.proxyChanged()

            return newob

        return repotool.getObjectRevision(docid, rev)

    # XXX was def getProxyInfoFromRepoId(self, repoid, workflow_vars=()):
    security.declarePublic('getProxyInfosFromDocid')
    def getProxyInfosFromDocid(self, docid, workflow_vars=()):
        """Get the proxy infos from a docid.

        Info is a dict with:

        - object: the proxy

        - rpath: the proxy path relative to the portal

        - visible: a boolean describing the visibility of the proxy

        - language_revs: the revisions for each language

        - all specified workflow vars.

        (Called by user code to get object full history.)
        """
        wftool = getToolByName(self, 'portal_workflow')
        portal = aq_parent(aq_inner(self))
        rpaths = self._docid_to_rpaths[docid]
        res = []
        for rpath in rpaths:
            try:
                ob = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', DEBUG,
                    'getProxiesFromRepoId no ob rpath=%s' % rpath)
                continue
            docid2, language_revs = self._rpath_to_infos[rpath]
            visible = _checkPermission(View, ob)
            info = {'object': ob,
                    'rpath': rpath,
                    'language_revs': language_revs,
                    'visible': visible,
                    }
            for var in workflow_vars:
                info[var] = wftool.getInfoFor(ob, var, None)
            res.append(info)
        return res

    # XXX was def getProxiesFromId(self, id):
    security.declarePublic('getProxiesFromObjectId')
    def getProxiesFromObjectId(self, id):
        """Get the proxy infos from an object id (gotten from the catalog).

        Returns a list of dictionnaries with:

        - object: the proxy

        - rpath: the proxy's rpath

        - docid: the proxy docid

        - language_revs: the association between language and revs

        Only returns the proxies that are visible.

        (Called by user code after a catalog search.)
        XXX should be transformed into a full searchResults method XXX
        """
        repotool = getToolByName(self, 'portal_repository')
        portal = aq_parent(aq_inner(self))
        docid, rev = repotool.getDocidAndRevisionFromObjectId(id)
        if docid is None:
            return []
        rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
        res = []
        for rpath in rpaths:
            docid2, language_revs = self._rpath_to_infos[rpath]
            try:
                # XXX costly if search
                # XXX We should be able to filter by visibility directly
                ob = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', DEBUG,
                    'getProxiesFromObjectId rpath=%s id=%s' % (rpath, id))
                continue
            if _checkPermission(View, ob):
                info = {'object': ob,
                        'rpath': rpath,
                        'docid': docid,
                        'language_revs': language_revs.copy(),
                        }
                res.append(info)
        return res

    security.declarePrivate('_reindexProxiesForObject')
    def _reindexProxiesForObject(self, ob):
        """Reindex all the proxies corresponding to an object in the repo."""
        repotool = getToolByName(self, 'portal_repository')
        portal = aq_parent(aq_inner(self))
        docid, rev = repotool.getDocidAndRevisionFromObjectId(ob.getId())
        LOG('ProxyTool', DEBUG, '_reindexProxiesForObject docid=%s rev=%s'
            % (docid, rev))
        if docid is None:
            return
        rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
        for rpath in rpaths:
            docid2, language_revs = self._rpath_to_infos[rpath]
            try:
                # XXX costly if search
                # XXX We should be able to filter by visibility directly
                proxy = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', ERROR,
                    '_reindexProxiesForObject no rpath=%s id=%s' % (rpath, id))
                continue
            LOG('ProxyTool', DEBUG, '_reindexProxiesForObject reindexing '
                'rpath=%s' % rpath)
            proxy.reindexObject()

    # XXX implement this
    security.declarePublic('searchResults')
    def searchResults(self, **kw):
        """Return the proxies matching a search in the catalog.
        """
        raise NotImplementedError


    security.declarePrivate('freezeProxy')
    def freezeProxy(self, proxy):
        """Freeze a proxy.

        (Also called by ProxyBase.)
        """
        # XXX use an event?
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()
        for lang, rev in proxy._getLanguageRevisions().items():
            #LOG('ProxyTool', DEBUG, ' Freezeing repoid=%s v=%s'
            #    % (repoid, version_info))
            repotool.freezeRevision(docid, rev)

    def _unshareContent(self, proxy, repotool):
        """Unshare content of a proxy.

        Puts new revisions into a new docid.
        """
        docid = proxy.getDocid()
        new_docid = repotool.getFreeDocid()
        for lang, rev in proxy._getLanguageRevisions().items():
            new_ob, new_rev = repotool.copyRevision(docid, rev, new_docid)
            proxy.setLanguageRevision(lang, new_rev)
        proxy.setDocid(new_docid)
        proxy.setFromLanguageRevisions({})
        proxy.setTag(None)
        proxy.proxyChanged()

    def _unshareContentDoRecursion(self, proxy, repotool):
        """Unshare content, and recurse."""
        if not _isinstance(proxy, ProxyBase):
            return
        self._unshareContent(proxy, repotool)
        for subob in proxy.objectValues():
            self._unshareContentDoRecursion(subob, repotool)

    security.declarePrivate('unshareContentRecursive')
    def unshareContentRecursive(self, proxy):
        """Unshare content

        Called after a copy+paste for instance. This is recursive.
        """
        repotool = getToolByName(self, 'portal_repository')
        self._unshareContentDoRecursion(proxy, repotool)

    security.declarePrivate('setSecurity')
    def setSecurity(self, proxy, skip_rpath=None):
        """Reapply correct security info to the revisions of a proxy.

        If skip_rpath, don't take that rpath into account (used when a
        deletion is processed).

        (Called by ProxyBase and self.) XXX but should use an event
        """
        # XXX should not get directly an object... or should it?
        LOG('setSecurity', DEBUG, '--- proxy %s'
            % '/'.join(proxy.getPhysicalPath()))
        if not _isinstance(proxy, ProxyBase):
            return

        #import traceback
        #from StringIO import StringIO
        #s = StringIO()
        #traceback.print_stack(file=s)
        #LOG('setSecurity', DEBUG, 'called from tb:\n%s' % s.getvalue())

        # Gather revisions.
        docid = proxy.getDocid()
        revs = {}
        for lang, rev in proxy._getLanguageRevisions().items():
            revs[rev] = None
        revs = revs.keys()
        LOG('setSecurity', DEBUG, "gathered revisions %s" % `revs`)

        # Gather the rpaths of proxies pointing to any revision.
        rpaths = {}
        for rev in revs:
            # For each revision, get all the proxies pointing to it.
            # XXX
            # XXX NOTE, the object may not be in the indexes yet...
            # XXX _createObject -> _insertWorkflow -> _reindexWorkflowVariables
            # XXX -> reindex() -> setSecurity
            # XXX
            # XXX The CMF Add event is only sent after that...
            # XXX
            rev_rpaths = self._docid_rev_to_rpaths[(docid, rev)]
            for rpath in rev_rpaths:
                if rpath != skip_rpath:
                    rpaths[rpath] = None
        rpaths = rpaths.keys()
        #LOG('setSecurity', DEBUG, 'rpaths=%s' % (rpaths,))

        # Get user permissions for users that have a (merged) local role.
        allperms = self._getRelevantPermissions()
        #LOG('setSecurity', DEBUG, 'relevant perms %s' % (allperms,))
        userperms = {}
        portal = aq_parent(aq_inner(self))
        for rpath in rpaths:
            ob = portal.unrestrictedTraverse(rpath)
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
        #LOG('setSecurity', DEBUG, 'userperms=%s' % (userperms,))

        # Now set security on revisions.
        repotool = getToolByName(self, 'portal_repository')
        for rev in revs:
            repotool.setRevisionSecurity(docid, rev, userperms)

        # XXX should be sent also by the one sending an event instead of
        #     calling this directly
        # XXX why this notify ? we're not changing this proxy's security...
        evtool = getEventService(self)
        evtool.notify('sys_modify_security', proxy, {})


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
        if _isinstance(ti, FactoryTypeInformation):
            ob = self._constructInstance_fti(container, ti, id, *args, **kw)
        elif _isinstance(ti, ScriptableTypeInformation):
            ob = self._constructInstance_sti(container, ti, id, *args, **kw)
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

    security.declarePrivate('_addProxy')
    def _addProxy(self, proxy, rpath):
        """Add knowledge about a new proxy.

        Maintains internal indexes.
        """
        docid = proxy.getDocid()
        language_revs = proxy.getLanguageRevisions()

        self._rpath_to_infos[rpath] = (docid, language_revs)

        rpaths = self._docid_to_rpaths.get(docid, ())
        if rpath not in rpaths:
            rpaths = rpaths + (rpath,)
            self._docid_to_rpaths[docid] = rpaths
        else:
            LOG('ProxyTool', ERROR,
                'Index _docid_to_rpaths for %s already has rpath=%s: %s'
                % (docid, rpath, rpaths))
            raise ValueError, rpath

        revs = {}
        for lang, rev in language_revs.items():
            revs[rev] = None
        for rev in revs.keys():
            key = (docid, rev)
            rpaths = self._docid_rev_to_rpaths.get(key, ())
            if rpath not in rpaths:
                rpaths = rpaths + (rpath,)
                self._docid_rev_to_rpaths[key] = rpaths
            else:
                LOG('ProxyTool', ERROR,
                    'Index _docid_rev_to_rpaths for %s already has '
                    'rpath=%s: %s' % (key, rpath, rpaths))
                raise ValueError, rpath


    security.declarePrivate('_delProxy')
    def _delProxy(self, rpath):
        """Delete knowledge about a proxy.

        Maintains internal indexes.
        """
        docid, language_revs = self._rpath_to_infos[rpath]
        del self._rpath_to_infos[rpath]

        rpaths = list(self._docid_to_rpaths[docid])
        rpaths.remove(rpath)
        if rpaths:
            self._docid_to_rpaths[docid] = tuple(rpaths)
        else:
            del self._docid_to_rpaths[docid]

        revs = {}
        for lang, rev in language_revs.items():
            revs[rev] = None
        for rev in revs.keys():
            key = (docid, rev)
            rpaths = list(self._docid_rev_to_rpaths[key])
            rpaths.remove(rpath)
            if rpaths:
                self._docid_rev_to_rpaths[key] = tuple(rpaths)
            else:
                del self._docid_rev_to_rpaths[key]

    security.declarePrivate('_modifyProxy')
    def _modifyProxy(self, proxy, rpath):
        """Recompute knowledge about a proxy."""
        self._delProxy(rpath)
        self._addProxy(proxy, rpath)

    #
    # Event notification
    #

    security.declarePrivate('notify_proxy')
    def notify_proxy(self, event_type, object, infos):
        """Notification from the event service.

        Called when a proxy is added/deleted/modified.
        Updates internal indexes.
        """
        # XXX Called when a document is modified. Notifies the proxies
        # that they have implicitly been modified. (Would be used so
        # that Title is reindexed for instance.)

        if event_type in ('sys_add_object', 'sys_del_object',
                          'sys_modify_object', 'modify_object'):
            if _isinstance(object, ProxyBase):
                LOG('ProxyTool', DEBUG, 'Got %s for proxy %s'
                    % (event_type, '/'.join(object.getPhysicalPath())))
                rpath = infos['rpath']
                dodel = 0
                if event_type == 'sys_add_object':
                    self._addProxy(object, rpath)
                elif event_type == 'sys_modify_object':
                    self._modifyProxy(object, rpath)
                elif event_type == 'sys_del_object':
                    dodel = 1
                # Refresh security on the revisions.
                if dodel:
                    skip_rpath = rpath
                else:
                    skip_rpath = None
                self.setSecurity(object, skip_rpath=skip_rpath)
                if dodel:
                    # Must be done last...
                    self._delProxy(rpath)
                LOG('ProxyTool', DEBUG, '  ... done')
            else:
                repotool = getToolByName(self, 'portal_repository')
                if repotool.isObjectInRepository(object):
                    if event_type in ('sys_modify_object', 'modify_object'):
                        LOG('ProxyTool', DEBUG, 'Got %s for repoob %s'
                            % (event_type, '/'.join(object.getPhysicalPath())))
                        # Repo object was modified, reindex all the proxies.
                        self._reindexProxiesForObject(object)
                        LOG('ProxyTool', DEBUG, '  ... done')

    #
    # Management
    #

    security.declareProtected(ManagePortal, 'getRevisionsUsed')
    def getRevisionsUsed(self):
        """Return management info about all the proxies.

        Return a dict of {docid: dict of {rev: None}}
        """
        res = {}
        for rpath, infos in self._rpath_to_infos.items():
            docid, language_revs = infos
            for lang, rev in language_revs.items():
                res.setdefault(docid, {})[rev] = None
        return res

    security.declareProtected(ManagePortal, 'getBrokenProxies')
    def getBrokenProxies(self):
        """Return the broken proxies.

        Return a list of (rpath, infos).
        """
        portal = aq_parent(aq_inner(self))
        broken = []
        for rpath, infos in self._rpath_to_infos.items():
            try:
                ob = portal.unrestrictedTraverse(rpath)
            except (AttributeError, KeyError):
                broken.append((rpath, infos))
        return broken

    def _recurse_rebuild(self, ob, utool):
        """Rebuild all proxies recursively."""
        if not _isinstance(ob, ProxyBase):
            return
        rpath = utool.getRelativeUrl(ob)
        self._addProxy(ob, rpath)
        for subob in ob.objectValues():
            self._recurse_rebuild(subob, utool)

    security.declareProtected(ManagePortal, 'rebuildProxies')
    def rebuildProxies(self):
        """Rebuild all proxies."""
        utool = getToolByName(self, 'portal_url')
        portal = aq_parent(aq_inner(self))
        self._clear()
        # Use as roots all the subobs (1st level) of the portal.
        for ob in portal.objectValues():
            self._recurse_rebuild(ob, utool)

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Management',
         'action': 'manage_proxiesInfo',
        },
        {'label': 'Proxies',
         'action': 'manage_listProxies',
        },
        ) + SimpleItemWithProperties.manage_options

    security.declareProtected(ManagePortal, 'manage_proxiesInfo')
    manage_proxiesInfo = DTMLFile('zmi/proxy_proxiesInfo', globals())

    security.declareProtected(ManagePortal, 'manage_listProxies')
    manage_listProxies = DTMLFile('zmi/proxy_list_proxies', globals())

    security.declareProtected(ManagePortal, 'manage_purgeBrokenProxies')
    def manage_purgeBrokenProxies(self, REQUEST=None):
        """Purge the broken proxies."""
        broken = self.getBrokenProxies()
        for rpath, infos in broken:
            self._delProxy(rpath)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/manage_proxiesInfo?search=1'
                                  '?manage_tabs_message=Purged.')

InitializeClass(ProxyTool)
