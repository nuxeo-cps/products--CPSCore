import unittest
from Testing.ZopeTestCase import ZopeTestCase

class TestMisc(ZopeTestCase):
    def testCopyright(self):
        copyright = self._app().manage_copyright()
        self.assert_(copyright.find("Nuxeo CPS") >=0)

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(TestMisc)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
