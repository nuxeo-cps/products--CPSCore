"""\
Simple test for portal_elements
"""

import Zope
from Acquisition import aq_base, aq_parent, aq_inner
import unittest

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SecurityManager import setSecurityPolicy
from Testing.makerequest import makerequest
from security import PermissiveSecurityPolicy, AnonymousUser

from Products.NuxCPS3.EventServiceTool import EventServiceTool

class EventServiceToolTest(unittest.TestCase):
    """\
    Test portal_elements
    """

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
            compressed=0
        )
        self.assertEqual(len(evtool.getSubscribers()), 1)

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(EventServiceToolTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
