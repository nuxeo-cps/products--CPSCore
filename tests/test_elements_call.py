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

class DummyTypeInfo:

    def getActionById(self, id):
        if id == 'action1':
            return 'method1'
        elif id == 'action2':
            return 'method2'
        else:
            raise KeyError, id

class DummyObject:
    def method1(self):
        return 1234

    def method2(self):
        return [1, 2, 3, 4]

    def restrictedTraverse(self, name):
        return getattr(self, name)

    def getTypeInfo(self):
        return DummyTypeInfo()

class CallElementsTest(unittest.TestCase):
    """\
    Test elements API, except for specific cache
    """

    def test_0_simpleCallElement(self):
        """\
        Just sets and gets a simple call element
        """
        elements = getElements(dummy_setter)
        a = DummyObject()
        elements.setCallElement('NAME', a, 'method1')
        self.assertEqual(elements['NAME'], 1234)

    def test_1_simpleActionCallElement(self):
        """\
        Just sets and gets a simple call element
        """
        elements = getElements(dummy_setter)
        a = DummyObject()
        elements.setActionCallElement('NAME', a, 'action1')
        self.assertEqual(elements['NAME'], 1234)

    def test_2_callElementWithPlaceHolder(self):
        """\
        A call element where the object used is an element place holder
        """
        elements = getElements(dummy_setter)
        ph = elements.getElementPlaceHolder('OBJECT')
        elements.setCallElement('NAME', ph, 'method1')
        elements['OBJECT'] = DummyObject()
        self.assertEqual(elements['NAME'], 1234)
        elements.setActionCallElement('NAME2', ph, 'action1')
        self.assertEqual(elements['NAME2'], 1234)

    def test_3_callElementWithSequence(self):
        """\
        Test call elements with sequences
        """
        elements = getElements(dummy_setter)
        a = DummyObject()
        elements.appendCallElement('NAME', a, 'method1')
        elements.extendElement('NAME', [9, 8, 7, 6])
        elements.extendCallElement('NAME', a, 'method2')
        elements.appendElement('NAME', 5)
        self.assertEqual(elements['NAME'], [1234, 9, 8, 7, 6, 1, 2, 3, 4, 5])

    def test_4_actionCallElementWithSequence(self):
        """\
        Test action call elements with sequences
        """
        elements = getElements(dummy_setter)
        a = DummyObject()
        elements.appendActionCallElement('NAME', a, 'action1')
        elements.extendElement('NAME', [9, 8, 7, 6])
        elements.extendActionCallElement('NAME', a, 'action2')
        elements.appendElement('NAME', 5)
        self.assertEqual(elements['NAME'], [1234, 9, 8, 7, 6, 1, 2, 3, 4, 5])

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(CallElementsTest)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
