# (c) 2002 Nuxeo SARL <http://nuxeo.com>
# (c) 2002 Julien <mailto:jj@nuxeo.com>
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

from zLOG import LOG, ERROR
from DateTime import DateTime
import random
from types import StringType, UnicodeType, TupleType

from Globals import InitializeClass, DTMLFile
from Acquisition import aq_parent, aq_inner, aq_base
from AccessControl import ClassSecurityInfo

from BTrees.IOBTree import IOBTree
from BTrees.OIBTree import OIBTree
from OFS.Folder import Folder

from Products.CMFCore.utils import UniqueObject, SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens


CPSSubscriberDefinition_type = 'CPS Subscriber Definition'
CPSEventServiceTool_type = 'CPS Event Service Tool'


def randid():
    abs = random.randrange(1,2147483600)
    if random.random() < 0.5:
        return -abs
    else:
        return abs


# FakeEventService is for places where no event service is found
class FakeEventService:
    def notify(self, *args, **kw):
        pass

fake_event_service = FakeEventService()


def getEventService(context):
    """Return the event service relative to context."""
    return getToolByName(context, 'portal_eventservice', fake_event_service)


class SubscriberDef(SimpleItemWithProperties):
    """Subscriber definition is used by Event Service tool.

    It just defines a subscriber to notify on some event.
    """

    meta_type = CPSSubscriberDefinition_type

    security = ClassSecurityInfo()
    security.declareObjectProtected(ViewManagementScreens)

    _properties = (
        {
            'id': 'subscriber',
            'type': 'string',
            'mode': 'w',
            'label': 'Subscriber',
        },
        {
            'id': 'action',
            'type': 'string',
            'mode': 'w',
            'label': 'Action',
        },
        {
            'id': 'meta_type_',
            'type': 'string',
            'mode': 'w',
            'label': 'Meta Type',
        },
        {
            'id': 'event_type',
            'type': 'tokens',
            'mode': 'w',
            'label': 'Event Type',
        },
        {
            'id': 'notification_type',
            'type': 'selection',
            'mode': 'w',
            'label': 'Notification Type',
            'select_variable': 'notification_types', # Acquired from tool
        },
        {
            'id': 'compressed',
            'type': 'boolean',
            'mode': 'w',
            'label': 'Compressed',
        },
    )

    def __init__(self, id, subscriber, action, meta_type,
                 event_type, notification_type,
                 compressed):
        self.id = id
        self.subscriber = subscriber
        self.action = action
        self.meta_type_ = meta_type
        self.event_type = event_type
        self.notification_type = notification_type
        self.compressed = compressed

    def _refresh(self, exclude_id=None):
        parent = aq_parent(aq_inner(self))
        if parent is not None and parent.meta_type == CPSEventServiceTool_type:
            parent._refresh_notification_dict(exclude_id=exclude_id)

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
        if aq_base(self) is aq_base(item):
            self._refresh()

    def manage_beforeDelete(self, item, container):
        """Force Event service tool to refresh its notification dict.
        """
        SimpleItemWithProperties.manage_beforeDelete(self, item, container)
        if aq_base(self) is aq_base(item):
            self._refresh(exclude_id=item.getId())

InitializeClass(SubscriberDef)


class EventServiceTool(UniqueObject, Folder):
    """Event service is used to dispatch notifications to subscribers.
    """

    id = 'portal_eventservice'
    meta_type = CPSEventServiceTool_type

    security = ClassSecurityInfo()

    notification_types = ('synchronous', )

    def __init__(self, *args, **kw):
        self._notification_dict = {}
        # location is a path relative to the root of the portal,
        # without an initial slash.
        #   '' = portal, 'Members' = members dir, etc.
        self._hubid_to_rlocation = IOBTree()
        self._rlocation_to_hubid = OIBTree()
        """
        # notification_dict is typically:
        {'add_object': {'folder': {'synchronous': [{'subscriber': 'portal_foo',
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
         # And portal_foo.notify_mymeth('add_object', object, infos) will
         # be called.
         """

    #
    # API
    #

    security.declarePublic('notify')
    def notify(self, event_type, object, infos):
        """Notifies subscribers of an event

        Passed infos is {'args': args, 'kw': kw} for add_object/del_object
        """
        hubid = self._objecthub_notify(event_type, object, infos)
        infos['hubid'] = hubid
        notification_dict = self._notification_dict
        portal = aq_parent(aq_inner(self))
        for ev_type in (event_type, '*'):
            event_def = notification_dict.get(ev_type)
            if event_def is not None:
                for me_type in (object.meta_type, '*'):
                    type_def = event_def.get(me_type)
                    if type_def is not None:
                        not_def = type_def.get('synchronous')
                        if not_def is not None:
                            for sub_def in not_def:
                                subscriber_id = sub_def['subscriber']
                                action = sub_def['action']
                                subscriber = getattr(
                                    portal, subscriber_id, None
                                )
                                if subscriber is not None:
                                    meth = getattr(subscriber, action)
                                    meth(event_type, object, infos)

    #
    # ObjectHub API
    #

    security.declarePublic('getHubId')
    def getHubId(self, object_or_location):
        """Get the hubid of an object or location, or None."""
        t = type(object_or_location)
        if t in (StringType, UnicodeType):
            location = object_or_location
        elif t == TupleType:
            location = '/'.join(object_or_location)
        else:
            location = '/'.join(object_or_location.getPhysicalPath())
        rlocation = self.get_rlocation(location)
        if rlocation is None:
            LOG('EventServiceTool', ERROR,
                'Hub: getHubId for bad location %s' % location)
            return None
        return self._rlocation_to_hubid.get(rlocation)

    security.declarePublic('getLocation')
    def getLocation(self, hubid, relative=0):
        """Get the location of a hubid, or None."""
        rlocation = self._hubid_to_rlocation.get(hubid)
        if rlocation is None:
            LOG('EventServiceTool', ERROR,
                'Hub: getLocation for bad hubid %s' % hubid)
            return None
        if relative:
            return rlocation
        utool = getToolByName(self, 'portal_url')
        ppath = utool.getPortalPath()
        if rlocation:
            return '%s/%s' % (ppath, rlocation)
        else:
            return ppath

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
            event_lists = sub_def.event_type
            for ev_type in event_lists:
                event_def = notification_dict.setdefault(ev_type, {})
                type_def = event_def.setdefault(sub_def.meta_type_, {})
                not_def = type_def.setdefault(sub_def.notification_type, [])
                not_def.append({
                    'subscriber': sub_def.subscriber,
                    'action': 'notify_%s' % (sub_def.action, ),
                    'compressed': sub_def.compressed,
                })
        self._notification_dict = notification_dict

    #
    # ObjecHub misc
    #

    def _get_rlocation(self, location):
        """Get a rlocation from a location.

        A rlocation is a location relative to the portal root.
        Returns '' for the portal itself.
        Returns None if the passed location is not under the portal.
        """
        if not location.startswith('/'):
            return location
        # make relative to portal
        utool = getToolByName(self, 'portal_url')
        ppath = utool.getPortalPath()
        if not location.startswith(ppath):
            # not under the portal
            return None
        location = location[len(ppath)+1:]
        return location

    def _generate_hubid(self, rlocation):
        """Generate and register a new hubid for a rlocation.

        Returns then new hubid.
        """
        index = getattr(self, '_v_nextid', 0)
        if index % 4000 == 0:
            index = randid()
        hubid_to_rlocation = self._hubid_to_rlocation
        while not hubid_to_rlocation.insert(index, rlocation):
            index = randid()
        self._rlocation_to_hubid[rlocation] = index
        self._v_nextid = index + 1
        return index

    def _objecthub_notify(self, event_type, object, infos):
        """Treat an event from the object hub's point of view."""
        location = '/'.join(object.getPhysicalPath())
        rlocation = self._get_rlocation(location)
        if rlocation is None:
            LOG('EventServiceTool', ERROR,
                'Hub: notify %s for bad location %s' % (event_type, location))
            return None
        if event_type == 'add_object':
            return self._register(rlocation)
        elif event_type == 'del_object':
            return self._unregister(rlocation)
        else:
            return self._rlocation_to_hubid.get(rlocation)

    def _register(self, rlocation):
        """Register a location and return its hubid."""
        if self._rlocation_to_hubid.has_key(rlocation):
            LOG('EventServiceTool', ERROR,
                'Hub: attempted to re-register location %s' % rlocation)
            return self._rlocation_to_hubid[rlocation]
        return self._generate_hubid(rlocation)

    def _unregister(self, rlocation):
        """Unregister a location and return the hubid it had."""
        hubid = self._rlocation_to_hubid.get(rlocation)
        if hubid is None:
            LOG('EventServiceTool', ERROR,
                'Hub: attempted to unregister unknown location %s' % rlocation)
            return None
        del self._rlocation_to_hubid[rlocation]
        del self._hubid_to_rlocation[hubid]
        return hubid

    #
    # ZMI
    #

    manage_options = (
        {
            'label': 'Subscribers',
            'action': 'manage_editSubscribersForm',
        },
        {
            'label': 'ObjectHub',
            'action': 'manage_listHubIds',
        },
        ) + Folder.manage_options[1:]


    security.declareProtected(ViewManagementScreens, 'manage_editSubscribersForm')
    manage_editSubscribersForm = DTMLFile('zmi/editSubscribersForm', globals())

    manage_main = manage_editSubscribersForm

    security.declareProtected(ViewManagementScreens, 'getSubscribers')
    def getSubscribers(self):
        """Return subscriber definitions."""
        return self.objectValues(CPSSubscriberDefinition_type)

    security.declareProtected(ViewManagementScreens, 'manage_addSubscriber')
    def manage_addSubscriber(self, subscriber, action, meta_type,
                             event_type, notification_type, compressed=0,
                             REQUEST=None):
        """Add a subscriber definition."""
        if type(event_type) is type(''):
            event_type = [event_type]
        id = 'subscriber_%s%s' % (int(DateTime()),
                                  random.randrange(100, 1000))
        subscriber_obj = SubscriberDef(id, subscriber, action, meta_type,
                                       event_type, notification_type,
                                       compressed)
        self._setObject(id, subscriber_obj)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(
                '%s/manage_editSubscribersForm' % (self.absolute_url(), )
            )

    #
    # HubId ZMI
    #

    security.declareProtected(ViewManagementScreens, 'manage_listHubIds')
    manage_listHubIds = DTMLFile('zmi/event_listHubIds', globals())

    security.declareProtected(ViewManagementScreens, 'manage_getHubIds')
    def manage_getHubIds(self):
        """Return all hubids and rlocations."""
        return self._rlocation_to_hubid.items()

InitializeClass(EventServiceTool)
