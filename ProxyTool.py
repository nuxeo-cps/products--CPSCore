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

from zLOG import LOG, ERROR, DEBUG
from Globals import InitializeClass
from Globals import PersistentMapping
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName


from Products.NuxCPS3.ProxyDocument import ProxyDocument_meta_type
ProxyMetaTypes = (ProxyDocument_meta_type,)

class ProxyTool(UniqueObject, Folder):
    """A proxy tool manages relationships between proxy objects
    and the documents they point to.

    The proxy tool must be registered with the event service to
    receive add_object and del_object, with action 'proxy'.
    """

    id = 'portal_proxies'
    meta_type = 'CPS Proxies Tool'

    security = ClassSecurityInfo()

    def __init__(self):
        self._hubid_to_info = PersistentMapping()

    #
    # API
    #

    security.declarePrivate('addProxy')
    def addProxy(self, hubid, repoid, version_filter):
        """Add a new proxy."""
        if self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR,
                'Adding already added hubid %s, repoid %s' % (hubid, repoid))
        self._hubid_to_info[hubid] = (repoid, version_filter)

    security.declarePrivate('delProxy')
    def delProxy(self, hubid):
        """Delete a proxy."""
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Deleting unknown hubid %s' % hubid)
        else:
            del self._hubid_to_info[hubid]

    security.declarePrivate('modifyProxy')
    def modifyProxy(self, hubid, repoid, version_filter):
        """Modify a proxy."""
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR,
                'Modifying unknown hubid %s, repoid %s' % (hubid, repoid))
        self.delProxy(hubid)
        self.addProxy(hubid, repoid, version_filter)

    security.declarePrivate('listProxies')
    def listProxies(self):
        """List all proxies."""
        return self._hubid_to_info.items()

    security.declarePrivate('getMatchedObject')
    def getMatchedObject(self, hubid):
        """Get the object best matched by a given proxy.

        Takes into account the filter.
        """
        repotool = getToolByName(self, 'portal_repository', None)
        if repotool is None:
            LOG('ProxyTool', ERROR, 'No portal_repository found')
            return None
        # XXX get preferred language here
        pref_lang = 'en' # XXX use Localizer methods
        if not self._hubid_to_info.has_key(hubid):
            LOG('ProxyTool', ERROR, 'Getting unknown hubid %s' % hubid)
            return None
        (repoid, version_filter) = self._hubid_to_info[hubid]
        # Find all available versions.
        version_infos = repotool.listVersions(repoid)
        # Find best match.
        version_info = self._get_best_version(version_infos, version_filter,
                                              pref_lang)
        if version_info is None:
            LOG('ProxyTool', DEBUG, 'Found no matching version for hubid %s, filter %s, infos %s' % (hubid, version_filter, version_infos))
            return None
        return repotool.getObjectVersion(repoid, version_info)

    security.declarePrivate('getMatchingProxies')
    def getMatchingProxies(self, repoid, version_info):
        """Get the proxies matching a given version of an object."""
        LOG('ProxyTool', ERROR, 'getMatchingProxies not implemented')
        return [] # XXX implement this


    security.declarePrivate('setSecurity')
    def setSecurity(self, secinfo):
        """Apply the security to the matching objects."""
        LOG('ProxyTool', ERROR, 'setSecurity not implemented')
        return

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
        if object.meta_type not in ProxyMetaTypes:
            return
        hubid = infos['hubid']
        if event_type == 'add_object':
            repoid = object.getRepoId()
            version_filter = object.getVersionFilter()
            self.addProxy(hubid, repoid, version_filter)
        elif event_type == 'del_object':
            self.delProxy(hubid)

    #
    # misc
    #

    def _get_best_version(version_infos, version_filter, pref_lang):
        """Find the best version in a list.

        This method has the knowledge if the structure of version_info.
        Returns a version_info or None.
        """
        wanted_ver = version_filter[0]
        if wanted_ver == None:
            # find the latest version
            wanted_ver = None
            for v in version_infos:
                ver = v[0]
                if wanted_ver is None or wanted_ver < ver:
                    wanted_ver = ver
        # keep only wanted version
        version_infos = [v for v in version_infos if v[0] == wanted_ver]
        if not version_infos:
            return None
        # find if language available
        for v in version_infos:
            if v[1] == pref_lang:
                return v
        # otherwise get first available version
        return version_infos[0]



InitializeClass(ProxyTool)
