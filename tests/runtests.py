# -*- coding: iso-8859-15 -*-
import os
from unittest import TestSuite, main
from sys import modules

def test_suite():
    names = os.listdir('.')
    testable_names = [name[:-3] for name in names \
                        if name.startswith('test_') and name.endswith('.py')]
    suite = TestSuite()
    for name in testable_names:
        __import__(name, globals(), locals())
        suite.addTest(modules[name].test_suite())
    return suite

if __name__ == '__main__':
    main(defaultTest='test_suite')
