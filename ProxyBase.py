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
from ExtensionClass import Base
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import AccessContentsInformation


class ProxyBase(Base):
    """Mixin class for proxy types.

    A proxy stores the repoid of the document family it points to,
    and a mapping of language -> version.
    """

    security = ClassSecurityInfo()

    def __init__(self, repoid, version_infos):
        self._repoid = repoid
        self._version_infos = version_infos

    security.declarePrivate('setVersionInfos')
    def setVersionInfos(self, version_infos):
        """Set the version infos for this proxy.

        The version infos is a dict of language -> version,
        where language can be '*' for the default, and version
        is an integer.
        """
        self._version_infos = version_infos.copy()

    security.declarePrivate('getVersionInfos')
    def getVersionInfos(self):
        """Return the version infos for this proxy."""
        return self._version_infos.copy()

    security.declarePrivate('getRepoId')
    def getRepoId(self):
        """Return the repoid for this proxy."""
        return self._repoid

    security.declareProtected(AccessContentsInformation, 'getObject')
    def getObject(self, lang=None):
        """Return the object referred to by this proxy."""
        pxtool = getToolByName(self, 'portal_proxies', None)
        if pxtool is None:
            LOG('ProxyBase', DEBUG, 'No portal_proxies found')
            return None
        hubtool = getToolByName(self, 'portal_eventservice', None)
        if hubtool is None:
            LOG('ProxyBase', DEBUG, 'No portal_eventservice found')
            return None
        hubid = hubtool.getHubId(self)
        if hubid is None:
            LOG('ProxyBase', ERROR,
                'No hubid found for %s' % '/'.join(self.getPhysicalPath()))
            return None
        return pxtool.getMatchedObject(hubid, lang=lang)

    #
    # Helpers
    #

    security.declarePublic('Title')
    def Title(self):
        """The object's title."""
        ob = self.getObject()
        if ob is not None:
            return ob.Title()
        else:
            return ''

    security.declarePublic('title_or_id')
    def title_or_id(self):
        """The object's title or id."""
        return self.getId()

    security.declarePublic('SearchableText')
    def SearchableText(self):
        """No searchable text."""
        return ''

InitializeClass(ProxyBase)
