# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Patch TypesTool so that TypeInformation's properties are editable.
"""

from AccessControl.PermissionRole import PermissionRole
from OFS.PropertyManager import PropertyManager
from Products.CMFCore.TypesTool import TypeInformation
from Products.CMFCore.TypesTool import FactoryTypeInformation as FTI
from Products.CMFCore.permissions import ManageProperties, View

TypeInformation.manage_propertiesForm = PropertyManager.manage_propertiesForm
TypeInformation.manage_addProperty__roles__ = PermissionRole(ManageProperties)
TypeInformation.manage_delProperties__roles__ = PermissionRole(ManageProperties)

ftiprops_ids = [p['id'] for p in FTI._properties]

if 'cps_is_searchable' not in ftiprops_ids:
    FTI._properties = FTI._properties + (
        {'id': 'cps_is_searchable', 'type': 'boolean', 'mode': 'w',
         'label': 'CPS Searchable'},
        )
    FTI.cps_is_searchable = 0

if 'cps_proxy_type' not in ftiprops_ids:
    FTI._properties = FTI._properties + (
        {'id': 'cps_proxy_type', 'type': 'selection', 'mode': 'w',
         'select_variable': 'getProxyTypesAllowed', 'label': 'CPS Proxytype'},
        )
    FTI.cps_proxy_type = ''

if 'cps_display_as_document_in_listing' not in ftiprops_ids:
    FTI._properties = FTI._properties + (
        {'id': 'cps_display_as_document_in_listing', 'type': 'boolean',
         'mode':'w', 'label': 'CPS Display as document in listing'},
        )
    FTI.cps_display_as_document_in_listing = 0


def getProxyTypesAllowed(self):
    """Return the list of allowed portal types strings"""
    return ['','document','folder','folderishdocument', 'btreefolder',
            'btreefolderishdocument']

FTI.getProxyTypesAllowed = getProxyTypesAllowed
FTI.getProxyTypesAllowed__roles__ = PermissionRole(View)
