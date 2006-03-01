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
"""CPS Site Properties XML Adapter.
"""

from zope.component import adapts
from zope.interface import implements
from Products.GenericSetup.utils import XMLAdapterBase
from Products.GenericSetup.utils import PropertyManagerHelpers

from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.interfaces import ISetupEnviron
from Products.CPSCore.interfaces import ICPSSite


PROPERTIES_NAME = 'properties'


class SitePropertiesXMLAdapter(XMLAdapterBase, PropertyManagerHelpers):
    """XML importer and exporter for cps site properties.

    Some properties are ignored during export or purge.
    """

    adapts(ICPSSite, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = PROPERTIES_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._doc.createElement('site')
        node.appendChild(self._extractProperties())
        self._logger.info("Site properties exported.")
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
        self._initProperties(node)
        self._logger.info("Site properties imported.")

    def _extractProperties(self):
        ignored = getattr(self.context, '_properties_genericsetup_noexport',())
        fragment = super(SitePropertiesXMLAdapter, self)._extractProperties()
        res = self._doc.createDocumentFragment()
        for node in fragment.childNodes:
            if node.nodeName != 'property':
                continue
            if node.getAttribute('name') in ignored:
                continue
            res.appendChild(node)
        return res

    def _purgeProperties(self):
        ignored = getattr(self.context, '_properties_genericsetup_nopurge', ())
        for prop_map in self.context._propertyMap():
            mode = prop_map.get('mode', 'wd')
            if 'w' not in mode:
                continue
            prop_id = prop_map['id']
            if prop_id in ignored:
                continue
            if 'd' in mode and not prop_id == 'title':
                self.context._delProperty(prop_id)
            else:
                prop_type = prop_map.get('type')
                if prop_type == 'multiple selection':
                    prop_value = ()
                elif prop_type in ('int', 'float'):
                    prop_value = 0
                else:
                    prop_value = ''
                self.context._updateProperty(prop_id, prop_value)
