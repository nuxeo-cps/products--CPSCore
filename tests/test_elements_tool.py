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

from Products.NuxCPS3.ElementsTool import ElementsTool

class ElementsToolTest(unittest.TestCase):
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
        tool = ElementsTool()
        portal._setObject(tool.getId(), tool)

    def _get_elements(self, path=None):
        self._make_tool()
        portal = self.root.testsite
        if path is None:
            object = portal
        else:
            object = portal.unrestrictedTraverse(path)
        portal_elements = portal.portal_elements
        return portal_elements.getElements(portal.REQUEST, object)

    def test_new(self):
        """\
        Test that creation of Elements tool is correct
        """
        self._make_tool()
        portal_elements = self.root.testsite.portal_elements
        self.assertEqual(portal_elements.meta_type, 'CPS Elements Tool')

    def test_get_elements(self):
        """\
        Test we can correctly get elements mapping
        """
        elements = self._get_elements()

    def test_default_elements(self):
        """\
        Test default elements sets in portal_elements
        """
        elements = self._get_elements()
        portal = self.root.testsite
        self.assertEqual(aq_base(elements['PORTAL']), aq_base(portal))
        self.assertEqual(aq_base(elements['CONTEXT']), aq_base(portal))
        self.assertEqual(aq_base(elements['CONTAINER']), aq_base(portal))
        self.assertEqual(aq_base(elements['NAVIGATION_BASE']), aq_base(portal))
        self.assertEqual(aq_base(elements['SITE_BASE']), aq_base(portal))
        self.assertEqual(elements['REQUEST'], self.root.REQUEST)

    def test_default_elements2(self):
        """\
        Test container/object default elements
        """
        portal = self.root.testsite
        Members = portal.Members
        index_html = Members.index_html
        elements = self._get_elements('Members/index_html')
        self.assertEqual(aq_base(elements['CONTAINER']), aq_base(Members))
        self.assertEqual(aq_base(elements['CONTEXT']), aq_base(index_html))
        self.assertEqual(aq_base(elements['PORTAL']), aq_base(portal))
        self.assertEqual(aq_base(elements['NAVIGATION_BASE']), aq_base(portal))
        self.assertEqual(aq_base(elements['SITE_BASE']), aq_base(portal))

    def test_bases_elements(self):
        """\
        Test container/object default elements
        """
        portal = self.root.testsite
        Members = portal.Members
        index_html = Members.index_html
        Members.manage_addProperty('NAVIGATION_BASE', 1, 'boolean')
        Members.manage_addProperty('SITE_BASE', 1, 'boolean')
        elements = self._get_elements('Members/index_html')
        self.assertEqual(aq_base(elements['CONTAINER']), aq_base(Members))
        self.assertEqual(aq_base(elements['CONTEXT']), aq_base(index_html))
        self.assertEqual(aq_base(elements['PORTAL']), aq_base(portal))
        self.assertEqual(aq_base(elements['NAVIGATION_BASE']), aq_base(Members))
        self.assertEqual(aq_base(elements['SITE_BASE']), aq_base(Members))


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(ElementsToolTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
