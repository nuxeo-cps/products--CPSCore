# (C) Copyright 2006-2007 Nuxeo SAS <http://nuxeo.com>
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
"""Base site for CPS.
"""

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

    cps_version = ('CPS', 3, 6, 1)
    cps_version_suffix = 'dev'

    _properties = (
        {'id': 'title', 'type': 'ustring',
         'label': 'Title', 'mode': 'w'},
        {'id': 'description', 'type': 'utext',
         'label': 'Description', 'mode': 'w'},
        {'id': 'last_upgraded_version', 'type': 'string',
         'label': 'Last upgraded version', 'mode': 'w'},
        {'id': 'available_languages', 'type': 'tokens',
         'label': 'Available languages', 'mode': 'w'},
        {'id': 'default_charset', 'type': 'string',
         'label': 'Default portal charset IS unicode', 'mode': 'r'},
        )
    last_upgraded_version = ''    # Initialized by installer or upgrader
    available_languages = ('en',) # Initialized by installer or importer
    default_charset = 'unicode'

    # The following properties are treated specially by GenericSetup
    # in the SitePropertiesXMLAdapter
    _properties_genericsetup_noexport = (
        'last_upgraded_version',
        )
    _properties_genericsetup_nopurge = (
        'last_upgraded_version',
        'available_languages',
        )

    # Override default OrderSupport behavior for ZMI convenience
    _default_sort_key = 'id'

    security = ClassSecurityInfo()

    security.declarePublic('getCPSVersion')
    def getCPSVersion(self):
        """Get CPS version as a tuple.
        """
        return self.cps_version

    def _setDefaultUpgradedVersion(self):
        """Set the default last_upgraded_version.

        Called by installer.
        """
        version = self.cps_version[1:] # skip 'CPS' part
        self.last_upgraded_version = '.'.join(map(str, version))

    def opaqueItems(self):
        """Performance shortcut.

        The mere fact that this is a CMFCatalogAware is a bit problematic.
        In any case without this, CMFCatalogAware.dispatchToOpaqueItems()
        function would dispatch all events (including BeforeTraverseEvent)
        to all attributes of the portal.

        This disabling saves a lot of render time in fast renderings, such as a
        single portlet from cache (30%) or a void response (304 etc.).
        """
        return ()

    opaqueValues = opaqueIds = opaqueItems


InitializeClass(CPSSite)
