import unittest
from zope.app.testing.placelesssetup import PlacelessSetup
from Testing.ZopeTestCase import ZopeTestCase

from zope.configuration import xmlconfig
import Products.CPSCore

ZOPE_VERSIONS = ('zope-2.9', 'zope-2.10')

class TestMisc(ZopeTestCase):
    def testCopyright(self):
        copyright = self._app().manage_copyright()
        self.assert_(copyright.find("Nuxeo CPS") >=0)

class TestZCMLMisc(PlacelessSetup, ZopeTestCase):

    def setUp(self):
        super(TestZCMLMisc, self).setUp()

        self.context = xmlconfig.file('meta.zcml',
                                      Products.CPSCore, execute=True)

    def tearDown(self):
        super(TestZCMLMisc, self).tearDown()

    def testZopeVersionAsFeature(self):
        for zv in ZOPE_VERSIONS:
            if self.context.hasFeature(zv):
                return

        self.fail(("None of the admitted %s are in ZCML context's "
                   "feature set." % repr(ZOPE_VERSIONS)))


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestMisc))
    suite.addTest(unittest.makeSuite(TestZCMLMisc))
    return suite
