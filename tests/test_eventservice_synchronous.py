# -*- coding: iso-8859-15 -*-
"""\
Simple test for portal_elements
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from Testing.makerequest import makerequest
from security import PermissiveSecurityPolicy, AnonymousUser

from Products.CPSCore.EventServiceTool import EventServiceTool

from dummy import DummySubscriber

class Class1:

    meta_type = 'type1'

    def getPhysicalPath(self, *args, **kw):
        return ('', 'testsite', 'instance1')

class Class2:

    meta_type = 'type2'

    def getPhysicalPath(self, *args, **kw):
        return ('', 'testsite', 'instance2')

class SynchronousNotificationsTest(unittest.TestCase):
    """Test portal_elements"""

    def setUp(self):
        get_transaction().begin()
        self._policy = PermissiveSecurityPolicy()
        self._oldPolicy = setSecurityPolicy(self._policy)
        self.connection = Zope.DB.open()
        self.root = self.connection.root()['Application']
        newSecurityManager(None, AnonymousUser().__of__(self.root))
        self.root = makerequest(self.root)

        from Products.CMFDefault.Portal import manage_addCMFSite
        manage_addCMFSite(self.root, 'testsite')

        portal = self.root.testsite
        self.portal = portal
        tool = EventServiceTool()
        portal._setObject(tool.getId(), tool)
        self.tool = getattr(portal, tool.getId())
        subscriber = DummySubscriber()
        portal._setObject(subscriber.getId(), subscriber)
        self.subscriber = getattr(portal, subscriber.getId())

    def tearDown(self):
        get_transaction().abort()
        self.connection.close()
        noSecurityManager()
        setSecurityPolicy(self._oldPolicy)

    def test_0_notification_by_type_and_event_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on object meta_type and event_type
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
        self.failUnless(subscriber.object is object)
        self.assertEqual(subscriber.infos['a'], 1)
        self.assertEqual(subscriber.notified, 1)

    def test_1_notification_by_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on object meta_type
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

    def test_2_notification_by_event_type(self):
        # Test that our subscriber is notified.
        # Filtering is done on event type
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

    def test_3_notification_no_filter(self):
        # Test that our subscriber is notified.
        # Don't filter
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

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(SynchronousNotificationsTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
