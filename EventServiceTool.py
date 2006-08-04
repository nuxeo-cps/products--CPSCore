# (C) Copyright 2002-2005 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Jalon
#          Florent Guillaume <fg@nuxeo.com>
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
"""Event Service

The Event Service receives events and dispatches them to interested parties.
"""

import sys
import random
import logging

from types import StringType
from DateTime import DateTime

from Globals import InitializeClass, DTMLFile
from Acquisition import aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from AccessControl import ModuleSecurityInfo
from AccessControl import Unauthorized
from AccessControl.Permissions import manage_properties
from ZODB.POSException import ConflictError

from OFS.OrderedFolder import OrderedFolder

import zope.event
from zope.app.container.contained import ObjectAddedEvent
from zope.app.container.contained import ContainerModifiedEvent
from zope.app.event.objectevent import ObjectModifiedEvent
from OFS.event import ObjectWillBeRemovedEvent

from zope.interface import implements
from Products.CPSCore.interfaces import IEventServiceTool
from Products.CPSCore.interfaces import IEventSubscriber

from Products.CMFCore.utils import UniqueObject, SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import ViewManagementScreens

from Products.CPSCore.events import securityModificationEvent

logger = logging.getLogger('CPSCore.EventServiceTool')
CPSSubscriberDefinition_type = 'CPS Subscriber Definition'
CPSEventServiceTool_type = 'CPS Event Service Tool'

# FakeEventService is for places where no event service is found
class FakeEventService:
    def notify(self, *args, **kw):
        pass
    notifyEvent = notify

fake_event_service = FakeEventService()


def getEventService(context):
    """Return the event service relative to context."""
    return getToolByName(context, 'portal_eventservice', fake_event_service)

class PublicEventService(object):
    security = ClassSecurityInfo()
    security.declareObjectPublic()
    security.setDefaultAccess('allow')
    def __init__(self, context):
        self.context = context
    def notifyEvent(self, event_type, ob, infos):
        evtool = getEventService(self.context)
        return evtool.notifyEvent(event_type, ob, infos)
InitializeClass(PublicEventService)

ModuleSecurityInfo('Products.CPSCore.EventServiceTool').declarePublic(
    'getPublicEventService')
def getPublicEventService(context):
    return PublicEventService(context)


class SubscriberDef(SimpleItemWithProperties):
    """Subscriber definition is used by Event Service tool.

    It just defines a subscriber to notify on some event.
    """

    implements(IEventSubscriber)

    meta_type = CPSSubscriberDefinition_type

    security = ClassSecurityInfo()
    security.declareObjectProtected(ViewManagementScreens)

    _properties = (
        {
            'id': 'subscriber',
            'type': 'string',
            'mode': 'w',
            'label': 'Subscriber',
        }, {
            'id': 'action',
            'type': 'string',
            'mode': 'w',
            'label': 'Action',
        }, {
            'id': 'meta_type_',
            'type': 'string',
            'mode': 'w',
            'label': 'Meta Type',
        }, {
            'id': 'event_type',
            'type': 'tokens',
            'mode': 'w',
            'label': 'Event Type',
        }, {
            'id': 'notification_type',
            'type': 'selection',
            'mode': 'w',
            'label': 'Notification Type',
            'select_variable': 'notification_types', # Acquired from tool
        }, {
            'id': 'compressed',
            'type': 'boolean',
            'mode': 'w',
            'label': 'Compressed',
        }, {
            'id': 'activated',
            'type': 'boolean',
            'mode': 'w',
            'label': 'Activated ?',
       },
    )

    activated = True

    def __init__(self, id, subscriber='', action='',
                 meta_type='*', event_type=('*',),
                 notification_type='synchronous',
                 compressed=False, activated=True):
        self.id = id
        self.subscriber = subscriber
        self.action = action
        self.meta_type_ = meta_type
        self.event_type = event_type
        self.notification_type = notification_type
        self.compressed = compressed
        self.activated = activated

    def _refresh(self, exclude_id=None):
        parent = aq_parent(aq_inner(self))
        if parent is not None and parent.meta_type == CPSEventServiceTool_type:
            parent._refresh_notification_dict(exclude_id=exclude_id)

    def enable(self):
        """Enable the subscriber
        """
        if not self.activated:
            self.activated = 1
            self._refresh()

    def disable(self):
        """Disable the subscriber
        """
        if self.activated:
            self.activated = 0
            self._refresh()

    def manage_changeProperties(self, REQUEST=None, **kw):
        """Change Subscriber definition properties and force Event service
        tool to refresh its notification dict.
        """
        result = SimpleItemWithProperties.manage_changeProperties(self, **kw)
        self._refresh()
        return result

    def manage_editProperties(self, REQUEST):
        """Change Subscriber definition properties and force Event service
        tool to refresh its notification dict.
        """
        result = SimpleItemWithProperties.manage_editProperties(self, REQUEST)
        self._refresh()
        return result

    def manage_afterAdd(self, item, container):
        """Force Event service tool to refresh its notification dict.
        """
        SimpleItemWithProperties.manage_afterAdd(self, item, container)
        self._refresh()

    def manage_beforeDelete(self, item, container):
        """Force Event service tool to refresh its notification dict.
        """
        SimpleItemWithProperties.manage_beforeDelete(self, item, container)
        self._refresh(exclude_id=self.getId())

InitializeClass(SubscriberDef)


class EventServiceTool(UniqueObject, OrderedFolder):
    """Event service is used to dispatch notifications to subscribers.
    """

    implements(IEventServiceTool)

    id = 'portal_eventservice'
    meta_type = CPSEventServiceTool_type

    security = ClassSecurityInfo()

    notification_types = ('synchronous', )

    def __init__(self, *args, **kw):
        self._notification_dict = {}
        """
        # notification_dict is typically:
        {'sys_add_object':
                 {'folder': {'synchronous': [{'subscriber': 'portal_foo',
                                              'action': 'notify_mymeth',
                                              'compressed': 0,
                                              },
                                             {'subscriber': 'portal_log',
                                              'action': 'notify_log',
                                              'compressed': 0,
                                              },
                                             ],
                             'asynchronous': [...],
                             },
                  '*': { ... },
                  },
         '*': { ... },
         }
         # And portal_foo.notify_mymeth('sys_add_object', object, infos) will
         # be called.
         """

    #
    # API
    #
    security.declarePrivate('notifyCompat')
    def notifyCompat(self, event_type, object, infos):
        """Notifies subscribers of an event

        infos is a dictionary with keys:
          rpath
          args, kw  (for sys_add_object, sys_del_object (unused))

        This method is private.
        """
        # Avoid using portal_url as sometimes we receive notifications before
        # the URL Tool exists.
        portal = aq_parent(aq_inner(self))
        pplen = len(portal.getPhysicalPath())
        rpath = '/'.join(object.getPhysicalPath()[pplen:])
        infos['rpath'] = rpath
        notification_dict = self._notification_dict
        exc_info = None
        try:
            for ev_type in (event_type, '*'):
                event_def = notification_dict.get(ev_type)
                if event_def is None:
                    continue
                for me_type in (object.meta_type, '*'):
                    type_def = event_def.get(me_type)
                    if type_def is None:
                        continue
                    not_def = type_def.get('synchronous')
                    if not_def is None:
                        continue
                    for sub_def in not_def:
                        # XXX before first refresh with prop
                        # the dict doesn't have the prop yet
                        if not sub_def.get('activated', 1):
                            continue
                        subscriber_id = sub_def['subscriber']
                        subscriber = getattr(portal, subscriber_id, None)
                        if subscriber is None:
                            logger.error('No subscriber %s', subscriber_id)
                            continue
                        action = sub_def['action']
                        try:
                            meth = getattr(subscriber, action)
                            meth(event_type, object, infos)
                        except ConflictError:
                            raise
                        except:
                            logger.error("Exception in subscriber",
                                         subscriber_id,
                                         exc_info=True)
                            if exc_info is None:
                                # Store this exception for later reraise
                                error = sys.exc_info()
                                exc_info = error
            # If there were exceptions, reraise the first one
            if exc_info is not None:
                raise exc_info[0], exc_info[1], exc_info[2]
        finally:
            # Cleanup potential reference to traceback object
            exc_info = None

    security.declarePublic('notifyEvent')
    def notifyEvent(self, event_type, object, infos):
        """Notifies subscribers of an event

        This method is public, so it cannot notify of system events.
        """
        if event_type.startswith('sys_'):
            raise Unauthorized, event_type
        return self.notify(event_type, object, infos)

    # BBB will be removed in CPS 3.5
    security.declarePrivate('notify')
    def notify(self, event_type, ob, infos):
        """Backward compatibility method for notifications.

        Does old processing and also redispatches as an event.
        """
        # Older CPS event tool subscribers notification
        self.notifyCompat(event_type, ob, infos)

        # Re-send as event
        if event_type == 'sys_del_object':
            parent = aq_parent(aq_inner(ob))
            zope.event.notify(ObjectWillBeRemovedEvent(ob, parent, ob.getId()))
        elif event_type in ('sys_add_object', 'sys_add_cmf_object'):
            parent = aq_parent(aq_inner(ob))
            zope.event.notify(ObjectAddedEvent(ob, parent, ob.getId()))
        elif event_type == 'sys_order_object':
            zope.event.notify(ContainerModifiedEvent(ob))
        elif event_type in ('sys_modify_object', 'modify_object'):
            zope.event.notify(ObjectModifiedEvent(ob))
        elif event_type == 'sys_modify_security':
            self._notifySecurityRecursively(ob)

    def _notifySecurityRecursively(self, ob):
        # Backward compat for old notify not dispatched to sublocations,
        # do the dispatching "by hand"
        zope.event.notify(securityModificationEvent(ob))
        for subob in ob.objectValues():
            self._notifySecurityRecursively(subob)

    #
    # misc
    #
    def _refresh_notification_dict(self, exclude_id=None):
        """Refresh notification dict."""
        ids = self.objectIds(CPSSubscriberDefinition_type)
        if exclude_id is not None:
            ids = [id for id in ids if id != exclude_id]
        notification_dict = {}
        for id in ids:
            sub_def = getattr(self, id)
            if not sub_def.subscriber:
                # Subscriber not fully initialized (event during its creation)
                continue
            event_lists = sub_def.event_type
            for ev_type in event_lists:
                event_def = notification_dict.setdefault(ev_type, {})
                type_def = event_def.setdefault(sub_def.meta_type_, {})
                not_def = type_def.setdefault(sub_def.notification_type, [])
                not_def.append({
                    'subscriber': sub_def.subscriber,
                    'action': 'notify_%s' % (sub_def.action, ),
                    'compressed': sub_def.compressed,
                    'activated' : sub_def.activated,
                })
        self._notification_dict = notification_dict

    security.declareProtected(manage_properties, 'moveObjectsByDelta')
    def moveObjectsByDelta(self, ids, delta, subset_ids=None):
        res = OrderedFolder.moveObjectsByDelta(self, ids, delta, subset_ids)
        self._refresh_notification_dict()
        return res

    #
    # ZMI
    #
    manage_options = (
        {
            'label': 'Subscribers',
            'action': 'manage_editSubscribersForm',
        },
        ) + OrderedFolder.manage_options[1:]


    security.declareProtected(ViewManagementScreens, 'manage_editSubscribersForm')
    manage_editSubscribersForm = DTMLFile('zmi/editSubscribersForm', globals())

    manage_editSubscribersForm._setName('manage_main')
    manage_main = manage_editSubscribersForm

    security.declareProtected(ViewManagementScreens, 'getSubscribers')
    def getSubscribers(self):
        """Return subscriber definitions."""
        return self.objectValues(CPSSubscriberDefinition_type)

    security.declareProtected(ViewManagementScreens, 'getSubscriberByName')
    def getSubscriberByName(self, name, default=None):
        """ Return a subscriber given it's name """
        for subscriber in self.getSubscribers():
            if subscriber.subscriber == name:
                return subscriber
        return default

    security.declareProtected(ViewManagementScreens, 'manage_addSubscriber')
    def manage_addSubscriber(self, subscriber, action, meta_type,
                             event_type, notification_type, compressed=0,
                             activated=1,
                             REQUEST=None):
        """Add a subscriber definition."""
        if isinstance(event_type, StringType):
            event_type = [event_type]

        # Create a new, unused, id
        while 1:
            id = 'subscriber_%s%s' % (int(DateTime()),
                                      random.randrange(100, 1000))
            if not id in self.objectIds():
                break
        subscriber_obj = SubscriberDef(id, subscriber, action, meta_type,
                                       event_type, notification_type,
                                       compressed, activated)
        self._setObject(id, subscriber_obj)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(
                '%s/manage_editSubscribersForm' % (self.absolute_url(),))
            return
        return id

InitializeClass(EventServiceTool)
