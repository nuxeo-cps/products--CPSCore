# -*- coding: iso-8859-15 -*-
from Testing import ZopeTestCase
from Products.CPSCore import utils

import unittest
import random
from OFS.ObjectManager import checkValidId

class Test(unittest.TestCase):

    def test_makeId(self):
        # example
        s1 = "C'est l'�t�!"
        self.assertEquals(utils.makeId(s1), "C_est_l_ete!")
        self.assertEquals(utils.makeId(s1, lower=1), "c_est_l_ete!")

        for i in range(0, 100):
            id = ''.join([chr(random.randint(32, 128)) for i in range(0, 10)])
            #checkValidId(utils.makeId(id))


    def test_isinstance(self):
        class A: pass
        class B: pass
        a = A()
        b = B()
        self.assert_(utils._isinstance(a, A))
        self.failIf(utils._isinstance(b, A))

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(Test)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
