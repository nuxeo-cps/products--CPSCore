# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Authors: Marc-Aurèle Darche <mad@nuxeo.com>
#          Hervé Cauwelier <hc@nuxeo.com>
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
# Replace MonkeyPatch of RegistrationTool by real object use
#
# $Id$

from re import match

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from OFS.PropertyManager import PropertyManager

from Products.CMFCore.CMFCorePermissions import AddPortalMember
from Products.CMFCore.utils import getToolByName
from Products.CMFDefault.RegistrationTool import RegistrationTool

# Patching the class

class CPSRegistrationTool(RegistrationTool, PropertyManager):
    """Replace MonkeyPatch of RegistrationTool by real object use."""

    meta_type = 'CPS Registration Tool'
    # allow e-mail-like ids
    allowed_member_id_pattern = "^[a-zA-Z][a-zA-Z0-9@\-\._]*$"

    _properties = (
        {'id': 'allowed_member_id_pattern', 'type': 'string', 'mode': 'w',
         'label': "Allowed member id pattern"},
    )

    manage_options = (PropertyManager.manage_options +
                      RegistrationTool.manage_options)

    security = ClassSecurityInfo()

    security.declareProtected(AddPortalMember, 'isMemberIdAllowed')
    def isMemberIdAllowed(self, id):
        """Returns 1 if the ID is not in use, is not reserved and the
        corresponding homeFolder doesn't already exists.
        """
        if len(id) < 1 or id == 'Anonymous User':
            return 0
        if not match(self.allowed_member_id_pattern, id):
            return 0
        membership = getToolByName(self, 'portal_membership')
        if (membership.getMemberById(id) is not None
                # Added: no duplicate home folder
                or membership.homeFolderExists(id)):
            return 0
        return 1

InitializeClass(CPSRegistrationTool)

def addCPSRegistrationTool(dispatcher, **kw):
    """Add a membership tool"""
    mt = CPSRegistrationTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)
