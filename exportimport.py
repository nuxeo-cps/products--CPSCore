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
"""CPS Core Tools XML Adapter.
"""

from Acquisition import aq_base
from zope.app import zapi
from zope.component import adapts
from zope.interface import implements
import Products
from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.utils import exportObjects
from Products.GenericSetup.utils import importObjects
from Products.GenericSetup.utils import BodyAdapterBase
from Products.GenericSetup.utils import XMLAdapterBase
from Products.GenericSetup.utils import ObjectManagerHelpers
from Products.GenericSetup.utils import PropertyManagerHelpers

from Products.GenericSetup.interfaces import INode
from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.interfaces import ISetupEnviron

from Products.CPSCore.interfaces import ITreeTool
from Products.CPSCore.interfaces import ITreeCache
from Products.CPSCore.interfaces import IEventServiceTool
from Products.CPSCore.interfaces import IEventSubscriber

from Products.CPSCore.EventServiceTool import SubscriberDef
from Products.CPSCore.EventServiceTool import CPSSubscriberDefinition_type


_marker = object()

TREE_TOOL = 'portal_trees'
TREE_NAME = 'trees'
EVENT_SERVICE_TOOL = 'portal_eventservice'
EVENT_SERVICE_NAME = 'eventservice'


def exportTreeTool(context):
    """Export Tree tool and tree caches as a set of XML files.
    """
    site = context.getSite()
    tool = getToolByName(site, TREE_TOOL, None)
    if tool is None:
        logger = context.getLogger(TREE_NAME)
        logger.info("Nothing to export.")
        return
    exportObjects(tool, '', context)

def importTreeTool(context):
    """Import tool and tree caches as a set of XML files.
    """
    site = context.getSite()
    tool = getToolByName(site, TREE_TOOL)
    importObjects(tool, '', context)


class TreeToolXMLAdapter(XMLAdapterBase, ObjectManagerHelpers):
    """XML importer and exporter for Tree tool.
    """
    adapts(ITreeTool, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = TREE_NAME
    name = TREE_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractObjects())
        self._logger.info("Tree tool exported.")
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeObjects()
        self._initObjects(node)
        self._logger.info("Tree tool imported.")


class TreeCacheXMLAdapter(XMLAdapterBase, PropertyManagerHelpers):
    """XML importer and exporter for a tree cache.
    """
    adapts(ITreeCache, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = TREE_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractProperties())
        self._logger.info("%s tree cache exported." % self.context.getId())
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
        self._initProperties(node)
        self._logger.info("%s tree cache imported." % self.context.getId())


def exportEventServiceTool(context):
    """Export event service tool and subscribers a set of XML files.
    """
    site = context.getSite()
    tool = getToolByName(site, EVENT_SERVICE_TOOL, None)
    if tool is None:
        logger = context.getLogger(EVENT_SERVICE_NAME)
        logger.info("Nothing to export.")
        return
    exportObjects(tool, '', context)

def importEventServiceTool(context):
    """Import event service tool and subscribers a set of XML files.
    """
    site = context.getSite()
    tool = getToolByName(site, EVENT_SERVICE_TOOL)
    importObjects(tool, '', context)

class EventServiceToolXMLAdapter(XMLAdapterBase, ObjectManagerHelpers):
    """XML importer and exporter for event service tool.
    """
    adapts(IEventServiceTool, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = EVENT_SERVICE_NAME
    name = EVENT_SERVICE_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractSubscribers())
        self._logger.info("Event service tool exported.")
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeSubscribers()
        self._initSubscribers(node)
        self._logger.info("Event service tool imported.")

    node = property(_exportNode, _importNode)

    def _extractSubscribers(self):
        fragment = self._doc.createDocumentFragment()
        for ob in self.context.getSubscribers():
            exporter = zapi.queryMultiAdapter((ob, self.environ), INode)
            if not exporter:
                raise ValueError(ob.getId())
            node = exporter.node
            fragment.appendChild(node)
        return fragment

    def _purgeSubscribers(self):
        self._purgeObjects()

    def _initSubscribers(self, node):
        tool = self.context
        for child in node.childNodes:
            if child.nodeName != 'object':
                continue
            id = str(child.getAttribute('name'))
            meta_type = str(child.getAttribute('meta_type'))
            if meta_type != CPSSubscriberDefinition_type:
                raise ValueError(meta_type)
            ob = SubscriberDef(id)
            tool._setObject(id, ob)
            ob = tool._getOb(id)
            importer = zapi.queryMultiAdapter((ob, self.environ), INode)
            if not importer:
                raise ValueError(id)
            importer.node = child
        pass

class EventSubscriberBodyAdapter(BodyAdapterBase, PropertyManagerHelpers):
    """Node importer and exporter for an event subscriber, no body.
    """

    adapts(IEventSubscriber, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = EVENT_SERVICE_NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractProperties())
        msg = "Event subscriber %r exported." % self.context.subscriber
        self._logger.info(msg)
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
        self._initProperties(node)
        self.context._refresh()
        msg = "Event subscriber %r imported." % self.context.subscriber
        self._logger.info(msg)

    node = property(_exportNode, _importNode)

    def _exportBody(self):
        return None

    def _importBody(self):
        pass

    body = property(_exportBody, _importBody)

