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

from DateTime import DateTime
from random import randrange
import OFS
from Globals import InitializeClass, DTMLFile
from Acquisition import aq_parent, aq_inner, aq_base
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import UniqueObject, SimpleItemWithProperties
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens

class SubscriberDef(SimpleItemWithProperties):
    """Subsriber definition is used by Event Service tool.

    It just defines a subsriber to notify on some event.
    """

    meta_type = 'CPS Subscriber Definition'

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
            'select_variable': 'notification_types',
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

    def manage_changeProperties(self, REQUEST=None, **kw):
        """Change Subsriber definition properties and force Event service
        tool to recalculate its notification dict.
        """
        result = SimpleItemWithProperties.manage_changeProperties(self, **kw)
        parent = aq_parent(aq_inner(self))
        if parent and parent.meta_type == 'CPS Event Service Tool':
            parent._calculate_notification_dict()
        return result

    def manage_editProperties(self, REQUEST):
        """Change Subsriber definition properties and force Event service
        tool to recalculate its notification dict.
        """
        result = SimpleItemWithProperties.manage_editProperties(self, REQUEST)
        parent = aq_parent(aq_inner(self))
        if parent and parent.meta_type == 'CPS Event Service Tool':
            parent._calculate_notification_dict()
        return result

    def manage_afterAdd(self, item, container):
        """Force Event service tool to recalculate its notification dict.
        """
        SimpleItemWithProperties.manage_afterAdd(self, item, container)
        if aq_base(self) is aq_base(item):
            container._calculate_notification_dict()

    def manage_beforeDelete(self, item, container):
        """Force Event service tool to recalculate its notification dict.
        """
        SimpleItemWithProperties.manage_beforeDelete(self, item, container)
        if aq_base(self) is aq_base(item):
            container._calculate_notification_dict(exclude_id=item.getId())

class EventServiceTool(UniqueObject, OFS.Folder.Folder):
    """Event service is used to dispatch notifications to subscribers.
    """

    id = 'portal_eventservice'

    meta_type = 'CPS Event Service Tool'

    security = ClassSecurityInfo()

    manage_options = (
        {
            'label': 'Subscribers',
            'action': 'manage_editSubscribersForm',
        },
    ) + OFS.Folder.Folder.manage_options[1:]

    notification_types = ('synchronous', )

    def __init__(self, *args, **kw):
        self._notification_dict = {}

    security.declarePublic('notify')
    def notify(self, event_type, object, infos):
        """Notifys subscribers of an event
        """
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

    def _calculate_notification_dict(self, exclude_id=None):
        """Calculate notification dict
        """
        ids = self.objectIds('CPS Subscriber Definition')
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

    # ZMI

    security.declareProtected(ViewManagementScreens, \
        'manage_editSubscribersForm')
    manage_editSubscribersForm = \
        DTMLFile('zmi/editSubscribersForm', globals())

    manage_main = manage_editSubscribersForm

    security.declareProtected(ViewManagementScreens, \
        'getSubscribers')
    def getSubscribers(self):
        """Return subscriber definitions
        """
        return self.objectValues('CPS Subscriber Definition')

    security.declareProtected(ViewManagementScreens, \
        'manage_addSubscriber')
    def manage_addSubscriber(self, subscriber, action, meta_type,
                              event_type, notification_type, compressed=0,
                              REQUEST=None):
        """Add a subscriber definition
        """
        if type(event_type) is type(''):
            event_type = [event_type]
        id = 'subscriber_%s%s' % (int(DateTime()), randrange(100, 1000))
        subscriber_obj = SubscriberDef(id, subscriber, action, meta_type,
                                       event_type, notification_type,
                                       compressed)
        self._setObject(id, subscriber_obj)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(
                '%s/manage_editSubscribersForm' % (self.absolute_url(), )
            )

InitializeClass(EventServiceTool)
