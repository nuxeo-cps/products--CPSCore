# -*- coding: iso-8859-15 -*-
"""
Simple test for event service
"""

from Testing import ZopeTestCase

ZopeTestCase.installProduct('CMFCore', quiet=1)
ZopeTestCase.installProduct('CMFDefault', quiet=1)
ZopeTestCase.installProduct('MailHost', quiet=1)
ZopeTestCase.installProduct('CPSCore', quiet=1)
ZopeTestCase.installProduct('ZCTextIndex', quiet=1)
import unittest

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from Testing.makerequest import makerequest
from Products.CMFCore.tests.base.security \
     import PermissiveSecurityPolicy, AnonymousUser

from Products.CPSCore.EventServiceTool import EventServiceTool

class EventServiceToolTest(ZopeTestCase.ZopeTestCase):
    """
    Test event service
    """

    def _make_tool(self):
        portal = self.folder
        tool = EventServiceTool()
        portal._setObject(tool.getId(), tool)

    def test_0_create(self):
        self._make_tool()

    def test_1_add_subscriber(self):
        self._make_tool()
        portal = self.folder
        evtool = portal.portal_eventservice
        evtool.manage_addSubscriber(
            subscriber='portal_subscriber',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
        )
        self.assertEqual(len(evtool.getSubscribers()), 1)

    def test_11_add_subscriber_without_activation_specified(self):
        self._make_tool()
        portal = self.folder
        evtool = portal.portal_eventservice
        evtool.manage_addSubscriber(
            subscriber='portal_subscriber',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
        )
        self.assertEqual(len(evtool.getSubscribers()), 1)
        sub = evtool.getSubscriberByName('portal_subscriber')
        self.assert_(sub.activated)

    def test_2_del_subscriber(self):
        self._make_tool()
        portal = self.folder
        evtool = portal.portal_eventservice

        # Subscriber 1
        id = evtool.manage_addSubscriber(
            subscriber='portal_subscriber',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        self.assert_(id)
        internal_subscribers = evtool._notification_dict['*']['*'][
            'asynchronous']
        self.assertEqual(len(evtool.getSubscribers()), 1)
        self.assertEqual(len(internal_subscribers),1)

        # Subscriber 2
        id2 = evtool.manage_addSubscriber(
            subscriber='portal_subscriber2',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        self.assert_(id2)
        self.assertEqual(len(evtool.getSubscribers()), 2)
        internal_subscribers = evtool._notification_dict['*']['*'][
            'asynchronous']
        self.assertEqual(len(internal_subscribers), 2)

        # Delete the subscriber 1
        evtool.manage_delObjects([id])
        internal_subscribers = evtool._notification_dict['*']['*'][
            'asynchronous']
        self.assertEqual(len(evtool.getSubscribers()), 1)
        self.assertEqual(len(internal_subscribers),1)

        # Delete the subscriber 2
        evtool.manage_delObjects([id2])
        self.assertEqual(len(evtool.getSubscribers()), 0)
        self.assertEqual(evtool._notification_dict,{})

    def test_2_getSubscriberByName(self):
        self._make_tool()
        portal = self.folder
        evtool = portal.portal_eventservice

        # Subscriber 1
        id = evtool.manage_addSubscriber(
            subscriber='portal_subscriber',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        # Subscriber 2
        id2 = evtool.manage_addSubscriber(
            subscriber='portal_subscriber2',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        # Test sub1
        sub1 = evtool.getSubscriberByName('portal_subscriber')
        self.assert_(sub1)
        self.assertEqual(sub1.getId(), id)

        # Test sub2
        sub2 = evtool.getSubscriberByName('portal_subscriber2')
        self.assert_(sub2)
        self.assertEqual(sub2.getId(), id2)

        # Test a non existent one
        subx = evtool.getSubscriberByName('portal_subscriber3')
        self.assertEqual(subx, None)

        # Test a non existent one with default returned value
        class Klass:
            pass

        instance = Klass()
        subx = evtool.getSubscriberByName('portal_subscriber3', instance)
        self.assertEqual(subx, instance)

    def test_order_subscribers(self):
        # XXX: assuming events are distributed in the order given by
        # getSubscribers() method
        self._make_tool()
        portal = self.folder
        evtool = portal.portal_eventservice

        # Subscriber 1
        id = evtool.manage_addSubscriber(
            subscriber='portal_subscriber1',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        # Subscriber 2
        id2 = evtool.manage_addSubscriber(
            subscriber='portal_subscriber2',
            action='action',
            meta_type="*",
            event_type="*",
            notification_type="asynchronous",
            compressed=0,
            activated=1,
            )

        subs_names = [x.subscriber for x in evtool.getSubscribers()]
        self.assertEqual(subs_names, ['portal_subscriber1',
                                      'portal_subscriber2'])

        # moving portal_subscriber2 on top
        subs = evtool.getSubscriberByName('portal_subscriber2')
        subs_id = subs.getId()
        evtool.moveObjectsToTop(ids=(subs_id,))

        subs_names = [x.subscriber for x in evtool.getSubscribers()]
        self.assertEqual(subs_names, ['portal_subscriber2',
                                      'portal_subscriber1'])

    # XXX: add more tests

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(EventServiceToolTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
