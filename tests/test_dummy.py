import unittest

class Test(unittest.TestCase):

    def setUp(self):
        self.dico = {}

    def tearDown(self):
        del self.dico

    def test_example(self):
        # example
        self.failUnlessEqual(0, len(self.dico))
        self.failUnlessRaises(KeyError, lambda x:x[1], self.dico)
        return 0


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(Test)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
