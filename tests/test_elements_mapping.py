"""\
Simple test elements mapping. Do not test Call elements
"""

import Zope
import unittest

from base import getElements

class DummyDefaultSetter:

    def _getDefaultElementsKeys(self):
        return []

    def _setDefaultElement(self, elements, name):
        raise ValueError, \
            'This setter does not knwo how to set %s' % (name, )

dummy_setter = DummyDefaultSetter()

class ElementsTest(unittest.TestCase):
    """\
    Test elements API, except for specific cache
    """

    def test_0_simpleSetGet(self):
        """\
        Just test elements as a simple mapping object
        """
        elements = getElements(dummy_setter)
        elements['NAME'] = 101
        self.assertEqual(elements['NAME'], 101)
        elements.set('NAME2', 102)
        self.assertEqual(elements.get('NAME2'), 102)

        # test other mapping methods
        self.assertEqual(elements.get('NAME3'), None)
        self.assertEqual(elements.get('NAME3', 103), 103)
        self.assertRaises(KeyError, lambda x:x['NAME3'], elements)
        self.failUnless(elements.has_key('NAME'))
        self.failUnless(not elements.has_key('NAME3'))

    def test_1_simpleSequence(self):
        """\
        Test a simple sequence
        """
        elements = getElements(dummy_setter)
        elements.appendElement('NAME', 1)
        self.assertEqual(elements['NAME'], [1])
        elements.extendElement('NAME', [2, 3])
        self.assertEqual(elements['NAME'], [1, 2, 3])

    def test_2_placeHolder(self):
        """\
        Test element place holders with simple setting/getting
        """
        elements = getElements(dummy_setter)
        elements['NAME'] = 1
        element_name = elements.getElementPlaceHolder('NAME')
        self.failUnless(getattr(element_name, '_isPlaceHolder', None))
        elements['NAME'] = 2
        self.assertEqual(element_name(), 2)
        element_name2 = elements.getElementPlaceHolder('NAME2')
        elements['NAME'] = element_name2
        elements['NAME2'] = 3
        self.assertEqual(elements['NAME'], 3)

    def test_3_appendPlaceHolderInSequence(self):
        """\
        Test element place holders in appending to sequences
        """
        elements = getElements(dummy_setter)
        one = elements.getElementPlaceHolder('ONE')
        elements.appendElement('NAME', one)
        elements.appendElement('NAME', 2)
        elements['ONE'] = 1
        self.assertEqual(elements['NAME'], [1, 2])
        three = elements.getElementPlaceHolder('THREE')
        elements.appendElement('NAME', three)
        elements['THREE'] = 3
        self.assertEqual(elements['NAME'], [1, 2, 3])

    def test_4_extendPlaceHolderInSequence(self):
        """\
        Test element place holder when extending sequences
        """
        elements = getElements(dummy_setter)
        elements['NAME'] = [1]
        two_three = elements.getElementPlaceHolder('TWO_THREE')
        elements.extendElement('NAME', two_three)
        elements['TWO_THREE'] = [2, 3]
        elements.extendElement('NAME', [4, 5])
        self.assertEqual(elements['NAME'], [1, 2, 3, 4, 5])

    def test_5_nocall(self):
        """\
        Verify that normal method/functions/callable objects
        are not called when getting
        """
        elements = getElements(dummy_setter)
        def f():
            raise 'Call error'
        elements['NAME'] = f
        try:
            a = elements['NAME']
        except 'Call error':
            self.fail()

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(ElementsTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
