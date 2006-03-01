# (C) Copyright 2005 Nuxeo SAS <http://nuxeo.com>
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
"""CPS Registration Tool XML Adapter.
"""

from zope.component import adapts
from zope.interface import implements
from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.utils import exportObjects
from Products.GenericSetup.utils import importObjects
from Products.GenericSetup.utils import XMLAdapterBase
from Products.GenericSetup.utils import PropertyManagerHelpers

from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.interfaces import ISetupEnviron
from Products.CMFCore.interfaces import IRegistrationTool


REGISTRATION_TOOL = 'portal_registration'
REGISTRATION_NAME = 'registration'


def exportRegistrationTool(context):
    """Export registration tool as an XML file.
    """
    site = context.getSite()
    tool = getToolByName(site, REGISTRATION_TOOL, None)
    if tool is None:
        logger = context.getLogger(REGISTRATION_NAME)
        logger.info("Nothing to export.")
        return
    exportObjects(tool, '', context)

def importRegistrationTool(context):
    """Import registration tool as an XML file.
    """
    site = context.getSite()
    tool = getToolByName(site, REGISTRATION_TOOL)
    importObjects(tool, '', context)


class RegistrationToolXMLAdapter(XMLAdapterBase, PropertyManagerHelpers):
    """XML importer and exporter for registration tool.
    """
    adapts(IRegistrationTool, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = REGISTRATION_NAME
    name = REGISTRATION_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractProperties())
        self._logger.info("Registration tool exported.")
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
        self._initProperties(node)
        self._logger.info("Registration tool imported.")
