"""\
Test a default element setter.
A default element setter is an object responsible of adding
elements if those elements were not already set
"""

import Zope
import unittest

from base import getElements

class DummyDefaultSetter:
    """\
    A simple default setter. With this setter, elements
    virtually contains elements 'NAME' (value: 1234),
    'LIST' (value [1, 2, 3, 4]), 'DUMMY' (no value but raises
    an exception if elements trys to get it from this setter)
    and 'DUMMY2' (which this setter promises to set but don't)
    """

    def _getDefaultElementsKeys(self):
        return ['NAME', 'LIST', 'DUMMY', 'DUMMY2']

    def _setDefaultElement(self, elements, name):
        if name == 'NAME':
            elements[name] = 1234
        elif name == 'LIST':
            elements[name] = [1, 2, 3, 4]
        elif name == 'DUMMY':
            # just to test this setter is never called for
            # this element
            raise 'DUMMY'
        elif name == 'DUMMY2':
            pass
        else:
            raise ValueError, \
                'This setter does not know how to set %s' % (name, )

dummy_setter = DummyDefaultSetter()

class SetterTest(unittest.TestCase):
    """\
    Test elements API, except for specific cache
    """

    def test_0_simpleTest(self):
        """\
        Test our default setter does its base job well
        """
        elements = getElements(dummy_setter)
        self.assertEqual(elements['NAME'], 1234)
        self.assertEqual(elements['LIST'], [1, 2, 3, 4])
        self.assertRaises('DUMMY', lambda x:x['DUMMY'], elements)
        # our setter does not do its job well since it promised
        # to set DUMMY2 but really don't...
        self.assertRaises(KeyError, lambda x:x['DUMMY2'], elements)

    def test_1_noNeedTest(self):
        """\
        Test that our setter is useless if we already set a default element
        """
        elements = getElements(dummy_setter)
        elements['NAME'] = 1
        self.assertEqual(elements['NAME'], 1)
        elements['DUMMY'] = 2
        self.assertEqual(elements['DUMMY'], 2)

    def test_2_sequenceTest(self):
        """\
        Test our default setter for a sequence
        """
        elements = getElements(dummy_setter)
        elements.appendElement('LIST', 5)
        self.assertEqual(elements['LIST'], [1, 2, 3, 4, 5])

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(SetterTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
