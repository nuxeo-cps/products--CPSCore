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

import unittest
import time

from Acquisition import aq_base, aq_parent, aq_inner
from OFS.Folder import Folder as OFS_Folder

from Products.CPSCore.EventServiceTool import EventServiceTool


class Folder(OFS_Folder):
    def __init__(self, id):
        self._setId(id)
        OFS_Folder.__init__(self)


class FakeUrlTool(Folder):
    def getRelativeUrl(self, ob):
        bself = aq_base(self)
        res = []
        while aq_base(ob) is not bself:
            res.insert(0, ob.getId())
            ob = aq_parent(aq_inner(ob))
            if ob is None:
                break
        return '/'.join(res)


class SomeException(Exception): pass

class DummySubscriber(Folder):
    notified = 0
    def notify_action(self, event_type, object, infos):
        if self.getId() == 'buggy' and infos.get('bug'):
            raise SomeException("Uncaught exception in subscriber")
        self.notified += 1
        self.object = object
        self.event_type = event_type
        self.infos = infos
        self.time = time.time()


class Class1:
    meta_type = 'type1'
    def getId(self):
        return 'instance1'

class Class2:
    meta_type = 'type2'
    def getId(self):
        return 'instance2'


class SynchronousNotificationsTest(unittest.TestCase):
    """Test portal_elements"""

    def makeInfrastructure(self):
        portal = self.portal = Folder('portal')
        portal.portal_url = FakeUrlTool('portal_url')

        tool = EventServiceTool()
        portal._setObject(tool.getId(), tool)
        self.tool = getattr(portal, tool.getId())

        subscriber = DummySubscriber('foo')
        portal._setObject(subscriber.getId(), subscriber)
        self.subscriber = getattr(portal, subscriber.getId())


    def test_notification_by_type_and_event_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on object meta_type and event_type.
        self.makeInfrastructure()
        tool = self.tool
        subscriber = self.subscriber
        tool.manage_addSubscriber(
            subscriber=subscriber.getId(),
            action='action',
            meta_type="type1",
            event_type="an_event",
            notification_type="synchronous",
            compressed=0
        )
        object = Class1()
        object2 = Class2()

        tool.notify('an_other_event', object, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_event', object2, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_other_event', object2, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_event', object, {'a': 1})
        self.assertEqual(subscriber.event_type, 'an_event')
        self.assert_(subscriber.object is object)
        self.assertEqual(subscriber.infos['a'], 1)
        self.assertEqual(subscriber.notified, 1)

    def test_notification_by_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on object meta_type.
        self.makeInfrastructure()
        tool = self.tool
        subscriber = self.subscriber
        tool.manage_addSubscriber(
            subscriber=subscriber.getId(),
            action='action',
            meta_type="type1",
            event_type="*",
            notification_type="synchronous",
            compressed=0
        )
        object = Class1()
        object2 = Class2()

        tool.notify('an_other_event', object2, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_event', object2, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_event', object, {})
        self.assertEqual(subscriber.notified, 1)
        tool.notify('an_other_event', object, {})
        self.assertEqual(subscriber.notified, 2)

    def test_notification_by_event_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on event type.
        self.makeInfrastructure()
        tool = self.tool
        subscriber = self.subscriber
        tool.manage_addSubscriber(
            subscriber=subscriber.getId(),
            action='action',
            meta_type="*",
            event_type="an_event",
            notification_type="synchronous",
            compressed=0
        )
        object = Class1()
        object2 = Class2()

        tool.notify('an_other_event', object, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_other_event', object2, {})
        self.assertEqual(subscriber.notified, 0)
        tool.notify('an_event', object, {})
        self.assertEqual(subscriber.notified, 1)
        tool.notify('an_event', object2, {})
        self.assertEqual(subscriber.notified, 2)

    def test_notification_no_filter(self):
        # Test that our subscriber is notified.
        # Don't filter.
        self.makeInfrastructure()
        tool = self.tool
        subscriber = self.subscriber
        tool.manage_addSubscriber(
            subscriber=subscriber.getId(),
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="synchronous",
            compressed=0
        )
        object = Class1()
        object2 = Class2()

        tool.notify('an_other_event', object, {})
        self.assertEqual(subscriber.notified, 1)
        tool.notify('an_other_event', object2, {})
        self.assertEqual(subscriber.notified, 2)
        tool.notify('an_event', object, {})
        self.assertEqual(subscriber.notified, 3)
        tool.notify('an_event', object2, {})
        self.assertEqual(subscriber.notified, 4)

    def test_notification_exception_robustness(self):
        # Test that if a subscriber causes an exception,
        # the other subscribers are still called.
        # Needed during delete notification.
        self.makeInfrastructure()
        tool = self.tool
        subscriber = self.subscriber
        buggy = DummySubscriber('buggy')
        self.portal._setObject('buggy', buggy)

        tool.manage_addSubscriber(
            subscriber='buggy',
            action='action',
            meta_type="*",
            event_type="an_event",
            notification_type="synchronous",
            compressed=0
        )
        tool.manage_addSubscriber(
            subscriber=subscriber.getId(),
            action='action',
            meta_type="*",
            event_type="an_event",
            notification_type="synchronous",
            compressed=0
        )

        object = Class1()

        # Check ordering of event subscribers
        tool.notify('an_event', object, {})
        self.assertEqual(buggy.notified, 1)
        self.assertEqual(subscriber.notified, 1)
        self.assert_(buggy.time < subscriber.time)

        # Make the buggy one raise an exception
        self.assertRaises(SomeException, tool.notify,
                          'an_event', object, {'bug': 1})

        # Check that the other subscriber was notified.
        self.assertEqual(subscriber.notified, 2)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(SynchronousNotificationsTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
