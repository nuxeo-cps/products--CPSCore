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
    """Mixin class for proxy types."""

    security = ClassSecurityInfo()

    def __init__(self, repoid, version_filter):
        self._repoid = repoid
        self._version_filter = version_filter

    security.declarePrivate('getRepoId')
    def getRepoId(self):
        """Return the repoid for this proxy."""
        return self._repoid

    security.declarePrivate('getVersionFilter')
    def getVersionFilter(self):
        """Return the version filter for this proxy."""
        return self._version_filter

    security.declareProtected(AccessContentsInformation, 'getObject')
    def getObject(self):
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
        return pxtool.queryMatchedObject(hubid)




InitializeClass(ProxyBase)
