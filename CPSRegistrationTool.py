# -*- coding: iso-8859-15 -*-
# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Authors: Marc-Aurèle Darche <madarche@nuxeo.com>
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
from Globals import InitializeClass, DTMLFile
from OFS.PropertyManager import PropertyManager

from zope.interface import implements
from Products.CMFCore.interfaces import IRegistrationTool

from Products.CMFCore.permissions import AddPortalMember
from Products.CMFCore.ActionInformation import ActionInformation
from Products.CMFCore.Expression import Expression
from Products.CMFCore.utils import getToolByName
from Products.CMFDefault.RegistrationTool import RegistrationTool


class CPSRegistrationTool(RegistrationTool, PropertyManager):
    """CPS Registration tool.
    """

    meta_type = 'CPS Registration Tool'

    _properties = (
        {'id': 'enable_portal_joining', 'type': 'boolean',
         'label': 'Enable portal joining', 'mode': 'w'},
        {'id': 'validate_email', 'type': 'boolean',
         'label': 'Validate email when joining', 'mode': 'w'},
        {'id': 'allowed_member_id_pattern', 'type': 'string',
         'label': "Allowed member id pattern", 'mode': 'w',
         },
        )
    enable_portal_joining = False
    validate_email = False
    allowed_member_id_pattern = "^[a-zA-Z][a-zA-Z0-9@\-\._]*$"

    _actions = ()

    manage_options = (PropertyManager.manage_options +      # Properties
                      RegistrationTool.manage_options[:1] + # Actions
                      RegistrationTool.manage_options[3:]   # Undo, etc.
                      )

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

    security.declarePublic('mailPassword')
    def mailPassword(self, forgotten_userid, REQUEST=None):
        """Delegate password emailing to the membership tool.
        """
        mtool = getToolByName(self, 'portal_membership')
        return mtool.mailPassword(forgotten_userid, REQUEST)

InitializeClass(CPSRegistrationTool)


def addCPSRegistrationTool(dispatcher, **kw):
    """Add a membership tool"""
    mt = CPSRegistrationTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)
