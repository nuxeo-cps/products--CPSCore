# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
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
from Globals import InitializeClass
from Globals import PersistentMapping
from Acquisition import aq_base
from AccessControl import ClassSecurityInfo

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName

from Products.NuxCPS3.ProxyBase import ProxyBase


class ProxyTool(UniqueObject, SimpleItemWithProperties):
    """A proxy tool manages relationships between proxy objects
    and the documents they point to.

    The proxy tool must be registered with the event service to receive
    add_object and del_object events, with action 'proxy'.
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
        """
        LOG('createProxy', DEBUG, 'Called with proxy_type=%s container=%s '
            'type_name=%s id=%s' % (proxy_type, container.getId(),
                                    type_name, id))
        if proxy_type == 'folder':
            proxy_type_name = 'CPS Proxy Folder'
        else:
            proxy_type_name = 'CPS Proxy Document'
        # Create the document in the repository
        repotool = getToolByName(self, 'portal_repository')
        repoid, version_info = repotool.invokeFactory(type_name, repoid=None,
                                                      version_info=None,
                                                      *args, **kw)
        # Create the proxy to that document
        # The proxy is a normal CMF object except that we change its
        # portal_type after construction.
        version_infos = {'*': version_info}
        # Note: this calls wf.notifyCreated() for all wf!
        if hasattr(aq_base(container), 'invokeFactoryCMF'):
            meth = container.invokeFactoryCMF
        else:
            meth = container.invokeFactory
        meth(proxy_type_name, id, repoid=repoid, version_infos=version_infos)
        # XXX should get new id effectively used! CMFCore bug!
        ob = container[id]
        # Set the correct portal_type for the proxy
        ob._setPortalTypeName(type_name)
        ob.reindexObject(idxs=['portal_type', 'Type'])
        return ob

    security.declarePrivate('listProxies')
    def listProxies(self):
        """List all proxies.

        Returns a sequence of (hubid, (repoid, version_infos)).
        NOTE that the version_infos mapping should not be mutated!
        """
        return self._hubid_to_info.items()

    security.declarePrivate('getMatchedObject')
    def getMatchedObject(self, hubid, lang=None):
        """Get the object best matched by a given proxy.

        Returns an object, or None if there is no match.
        If lang is not passed, takes into account the user language.
        """
        repotool = getToolByName(self, 'portal_repository', None)
        if repotool is None:
            LOG('ProxyTool', ERROR, 'No portal_repository found')
            return None
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Getting unknown hubid %s' % hubid)
            return None
        (repoid, version_infos) = self._hubid_to_info[hubid]
        if lang is None:
            # XXX get preferred language here - abstract the negociation
            # XXX use Localizer methods
            lang = '*'
        # Find version
        if version_infos.has_key(lang):
            version_info = version_infos[lang]
        elif version_infos.has_key('*'):
            version_info = version_infos['*']
        else:
            LOG('ProxyTool', DEBUG, 'Found no matching version for hubid %s, repoid %s, lang %s, infos %s' % (hubid, repoid, pref_lang, version_infos))
            return None
        return repotool.getObjectVersion(repoid, version_info)

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

    security.declarePrivate('setSecurity')
    def setSecurity(self, secinfo):
        """Apply the security to the matching objects."""
        LOG('ProxyTool', ERROR, 'setSecurity not implemented')
        return

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
        """
        if event_type not in ('add_object', 'del_object'):
            return
        if not isinstance(object, ProxyBase):
            return
        hubid = infos['hubid']
        if event_type == 'add_object':
            repoid = object.getRepoId()
            version_infos = object.getVersionInfos()
            self.addProxy(hubid, repoid, version_infos)
        elif event_type == 'del_object':
            self.delProxy(hubid)


InitializeClass(ProxyTool)
