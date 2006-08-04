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
"""CPS Event Service XML Adapter.
"""

from zope.app import zapi
from zope.component import adapts
from zope.interface import implements
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

from Products.CPSCore.interfaces import IEventServiceTool
from Products.CPSCore.interfaces import IEventSubscriber
from Products.CPSCore.EventServiceTool import SubscriberDef
from Products.CPSCore.EventServiceTool import CPSSubscriberDefinition_type


EVENT_SERVICE_TOOL = 'portal_eventservice'
EVENT_SERVICE_NAME = 'eventservice'


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

        after_clean = False
        before_ids = tool.objectIds()
        to_del = []
        for child in node.childNodes:
            if child.nodeName != 'object':
                continue
            id = str(child.getAttribute('name'))
            if not tool.hasObject(id):
                meta_type = str(child.getAttribute('meta_type'))
                if meta_type != CPSSubscriberDefinition_type:
                    raise ValueError(meta_type)
                ob = SubscriberDef(id)
                tool._setObject(id, ob)
                after_clean = True
            ob = tool._getOb(id)
            importer = zapi.queryMultiAdapter((ob, self.environ), INode)
            if not importer:
                raise ValueError(id)
            importer.node = child

            # clean tool from possible duplicate subscriber: old one
            # with same subscriber and action (ZMI creation has random ids)
            if id == 'subscriber_trees':
                import pdb; pdb.set_trace()
            if after_clean:
                discr = (ob.subscriber, ob.action)
                for b_id in before_ids:
                    b_ob = tool._getOb(b_id)
                    if (b_ob.subscriber, b_ob.action) == discr:
                        to_del.append(b_id)

        tool.manage_delObjects(to_del)

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
