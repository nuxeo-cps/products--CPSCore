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
"""Catalog Tool XML Adapter for CPS.
"""

from zope.component import adapts
from zope.interface import implements

from Products.GenericSetup.ZCatalog.exportimport import ZCatalogXMLAdapter
from Products.ZCatalog.ProgressHandler import ZLogHandler

from Products.GenericSetup.interfaces import INode
from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.interfaces import ISetupEnviron
from Products.CMFCore.interfaces import ICatalogTool


class CatalogToolXMLAdapter(ZCatalogXMLAdapter):
    """XML importer and exporter for the Catalog Tool.

    Repopulates indexes that have been added.
    """
    adapts(ICatalogTool, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = 'catalogtool'
    name = 'catalog'

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
            self._purgeObjects()
            self._purgeIndexes()
            self._purgeColumns()
        self._initProperties(node)
        self._initObjects(node)
        self._initIndexes(node)
        self._initColumns(node)

        if self.environ.shouldPurge():
            self._refreshCatalog()

        self._logger.info("Catalog tool imported.")

    def _refreshCatalog(self):
        """Refresh the catalog.
        """
        # We don't just refresh the changed indexes because
        # - this wouldn't readd metadata (columns)
        # - usually all indexes are reset anyway
        cat = self.context
        pgthreshold = cat._getProgressThreshold() or 100
        pghandler = ZLogHandler(pgthreshold)
        cat.refreshCatalog(clear=True, pghandler=pghandler)
