# -*- coding: iso-8859-15 -*-
from Testing import ZopeTestCase
from Products.CPSCore import utils

import unittest

class Test(unittest.TestCase):

    def test_makeId(self):
        # example
        s1 = "C'est l'été !"
        self.assertEquals(utils.makeId(s1), "C-est-l-ete")
        self.assertEquals(utils.makeId(s1, lower=1), "c-est-l-ete")

        s1 = "C'est !!! l'été !!!!"
        self.assertEquals(utils.makeId(s1), "C-est-l-ete")
        self.assertEquals(utils.makeId(s1, lower=1), "c-est-l-ete")

    def test_isinstance(self):
        class A: pass
        class B: pass
        a = A()
        b = B()
        self.assert_(utils._isinstance(a, A))
        self.failIf(utils._isinstance(b, A))

    def test_isUserAgentMsie(self):
        request = {'HTTP_USER_AGENT': "Mozilla/1.0"}
        self.assert_(not utils.isUserAgentMsie(request))
        request = {'HTTP_USER_AGENT': "MSIE"}
        self.assert_(utils.isUserAgentMsie(request))

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(Test)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
