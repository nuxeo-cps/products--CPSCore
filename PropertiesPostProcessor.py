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
"""PropertiesPostProcessor

Provide the opportunity to react after a ZMI properties change.
"""

from ExtensionClass import Base
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFCore.CMFCorePermissions import ManageProperties


class PropertiesPostProcessor(Base):
    """
    Provide the opportunity to react after a ZMI properties change.

    _propertiesBaseClass must be set to the class whose code we call
    to the the actual properties change.
    """

    security = ClassSecurityInfo()

    security.declareProtected(ManageProperties, 'manage_editProperties')
    def manage_editProperties(self, REQUEST):
        """Edit object properties via the web.

        Computes internal values for the acls.
        """
        self._propertiesBaseClass.manage_editProperties(self, REQUEST)
        self._postProcessProperties()
        if REQUEST is not None:
            message = "Saved changes."
            # XXX Will be rendered twice but what the heck...
            return self.manage_propertiesForm(self, REQUEST,
                                              manage_tabs_message=message)

    security.declareProtected(ManageProperties, 'manage_changeProperties')
    def manage_changeProperties(self, REQUEST=None, **kw):
        """Change existing object properties.

        Computes internal values for the acls.
        """
        if REQUEST is not None:
            for k, v in REQUEST.items():
                kw[k] = v
        self._propertiesBaseClass.manage_changeProperties(self, **kw)
        self._postProcessProperties()
        if REQUEST is not None:
            message = "Saved changes."
            return self.manage_propertiesForm(self, REQUEST,
                                              manage_tabs_message=message)

    def _postProcessProperties(self):
        """Post-processing after properties change."""
        pass

InitializeClass(PropertiesPostProcessor)
