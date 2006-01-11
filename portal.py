# (C) Copyright 2006 Nuxeo SAS <http://nuxeo.com>
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
"""Base  portal for CPS
"""

from zLOG import LOG, INFO, DEBUG
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFDefault.Portal import CMFSite

from zope.interface import implements
from Products.CPSCore.interfaces import ICPSSite

class CPSSite(CMFSite):
    """Base class for a CPS Site.
    """

    implements(ICPSSite)

    meta_type = 'CPS Site'
    portal_type = 'Portal'

    cps_version = ('CPS', 3, 4, 0)

    _properties = CMFSite._properties + (
        {'id': 'last_upgraded_version', 'type': 'string',
         'label': 'Last upgraded version', 'mode': 'w'},
        {'id': 'available_languages', 'type': 'tokens',
         'label': 'Available languages', 'mode': 'w'},
        )
    last_upgraded_version = '.'.join(map(str, cps_version[1:]))
    available_languages = ('en', 'fr') # Use by Localizer config XXX dehardcode

    # Override default OrderSupport behavior for ZMI convenience
    _default_sort_key = 'id'

    security = ClassSecurityInfo()

    security.declarePublic('getCPSVersion')
    def getCPSVersion(self):
        """ returns cps version
        """
        return self.cps_version

InitializeClass(CPSSite)
