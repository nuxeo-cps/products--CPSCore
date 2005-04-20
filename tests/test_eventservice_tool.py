# -*- coding: iso-8859-15 -*-
"""
Simple test for event service
"""

import Testing.ZopeTestCase.ZopeLite as Zope
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


class EventServiceToolTest(unittest.TestCase):
    """
    Test event service
    """

    # XXX: refactor this using ZopeTestCase
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

    def tearDown(self):
        get_transaction().abort()
        self.connection.close()
        noSecurityManager()
        setSecurityPolicy(self._oldPolicy)

    def _make_tool(self):
        portal = self.root.testsite
        tool = EventServiceTool()
        portal._setObject(tool.getId(), tool)

    def test_0_create(self):
        self._make_tool()

    def test_1_add_subscriber(self):
        self._make_tool()
        portal = self.root.testsite
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

    # XXX: add more tests

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(EventServiceToolTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
