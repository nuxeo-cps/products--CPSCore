# -*- coding: iso-8859-15 -*-
import unittest
from Testing.ZopeTestCase import ZopeTestCase

from Products.CPSCore.CPSWorkflowStacks import BaseStack, SimpleStack, \
     HierarchicalStack

from Interface.Verify import verifyClass
from Products.CPSCore.interfaces.IWorkflowStack import IWorkflowStack
from Products.CPSCore.interfaces.ISimpleWorkflowStack import \
     ISimpleWorkflowStack
from Products.CPSCore.interfaces.IHierarchicalWorkflowStack import \
     IHierarchicalWorkflowStack

class TestCPSWorkflowStacks(ZopeTestCase):

    def test_interface(self):

        verifyClass(IWorkflowStack, BaseStack)
        verifyClass(IWorkflowStack, SimpleStack)
        verifyClass(IWorkflowStack, HierarchicalStack)

        verifyClass(ISimpleWorkflowStack, SimpleStack)
        verifyClass(IHierarchicalWorkflowStack, HierarchicalStack)
        verifyClass(ISimpleWorkflowStack, HierarchicalStack)

    def test_BaseStackNoMaxSize(self):

        # Test Base Stack with no initialization
        bstack = BaseStack()
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Adding one element
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Adding same element. (Allowed with this stack)
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 2)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Adding another element. (Allowed with this stack)
        bstack.push('elt2')
        self.assertEqual(bstack.getSize(), 3)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop now
        elt = bstack.pop()
        self.assertEqual(elt, 'elt2')
        self.assertEqual(bstack.getSize(), 2)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Adding one element
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Try to push a None element
        res = bstack.push(None)
        self.assertEqual(res, -1)

    def test_BaseStackWithMaxSize(self):

        # Test Base Stack with no initialization
        bstack = BaseStack(maxsize=2)
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Adding one element
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Adding same element. (Allowed with this stack)
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 2)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 1)

        # Adding another element.
        # Stack is full now
        res = bstack.push('elt2')
        self.assertEqual(res, 0)
        self.assertEqual(bstack.getSize(), 2)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 1)

        # Pop now
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 0)
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Adding one element
        bstack.push('elt1')
        self.assertEqual(bstack.getSize(), 1)
        self.assertEqual(bstack.isEmpty(), 0)
        self.assertEqual(bstack.isFull(), 0)

        # Pop again
        elt = bstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(bstack.getSize(), 0)
        self.assertEqual(bstack.isEmpty(), 1)
        self.assertEqual(bstack.isFull(), 0)

        # Try to push a None element
        res = bstack.push(None)
        self.assertEqual(res, -1)

    def test_SimpleStackNoMaxSize(self):

        # Test Base Stack with no initialization
        sstack = SimpleStack()
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Adding one element
        sstack.push('elt1')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Adding same element. (Not allowed with this stack)
        res = sstack.push('elt1')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Adding another element. (Allowed with this stack)
        sstack.push('elt2')
        self.assertEqual(sstack.getSize(), 2)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Pop now
        elt = sstack.pop()
        self.assertEqual(elt, 'elt2')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 0)
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Adding one element
        sstack.push('elt1')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Try to push a None element
        res = sstack.push(None)
        self.assertEqual(res, -1)

    def test_SimpleStackWithMaxSize(self):

        # Test Base Stack with no initialization
        sstack = SimpleStack(maxsize=2)
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Adding one element
        sstack.push('elt1')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Adding same element. (Not allowed with this stack)
        res = sstack.push('elt1')
        self.assertEqual(res, -2)
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        self.assertEqual(sstack.getStackContent(), ['elt1'])

        # Adding another element.
        res = sstack.push('elt2')
        self.assertEqual(res, 1)

        self.assertEqual(sstack.getStackContent(), ['elt1','elt2'])

        self.assertEqual(sstack.getSize(), 2)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 1)

        # Pop now
        elt = sstack.pop()
        self.assertEqual(elt, 'elt2')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 0)
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Adding one element
        sstack.push('elt1')
        self.assertEqual(sstack.getSize(), 1)
        self.assertEqual(sstack.isEmpty(), 0)
        self.assertEqual(sstack.isFull(), 0)

        # Pop again
        elt = sstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(sstack.getSize(), 0)
        self.assertEqual(sstack.isEmpty(), 1)
        self.assertEqual(sstack.isFull(), 0)

        # Try to push a None element
        res = sstack.push(None)
        self.assertEqual(res, -1)

        sstack = SimpleStack()

        # Test the removeElement() method
        self.assertEqual(sstack.getStackContent(), [])
        self.assertEqual(sstack.removeElement('elt1'), 0)
        sstack.push('elt1')
        self.assertEqual(sstack.removeElement('elt1'), 1)
        sstack.push('elt1')
        sstack.push('elt2')
        self.assertEqual(sstack.getStackContent(), ['elt1', 'elt2'])
        sstack.push('elt3')
        self.assertEqual(sstack.getStackContent(), ['elt1', 'elt2', 'elt3'])
        self.assertEqual(sstack.removeElement('elt2'), 1)
        self.assertEqual(sstack.getStackContent(), ['elt1', 'elt3'])

        sstack.removeElement('elt3')
        sstack.removeElement('elt1')
        self.assertEqual(sstack.getStackContent(), [])

    def test_simpleHierarchicalStackNoMaxSize(self):

        #
        # This tests are all done at level 0 implicitly
        # They are the same as the one on the SimpleStack
        # The idea is to show it's possible the hierarchical stack
        # as a simple stack without having to care of the current level
        # It's just a validation of the implementation
        #

        # Test Base Stack with no initialization
        hstack = HierarchicalStack()
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Adding one element
        hstack.push('elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Adding same element. (Not allowed with this stack)
        res = hstack.push('elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Adding another element. (Allowed with this stack)
        hstack.push('elt2')
        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Pop now
        elt = hstack.pop()
        self.assertEqual(elt, 'elt2')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 0)
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Adding one element
        hstack.push('elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Try to push a None element
        res = hstack.push(None)
        self.assertEqual(res, -1)

        # direction
        self.assertEqual(hstack.getDirection(), 1)
        self.assertEqual(hstack.blockDirection(), 0)
        self.assertEqual(hstack.getDirection(), 0)
        self.assertEqual(hstack.setDirectionUp(), -1)
        self.assertEqual(hstack.getDirection(), -1)
        self.assertEqual(hstack.blockDirection(), 0)
        self.assertEqual(hstack.getDirection(), 0)
        self.assertEqual(hstack.setDirectionDown(), 1)
        self.assertEqual(hstack.getDirection(), 1)
        self.assertEqual(hstack.returnedUpDirection(), -1)
        self.assertEqual(hstack.returnedUpDirection(), 1)

    def test_HierarchicalStackNoMaxSizeWithLevels(self):

        #
        # Now this tests test the levels
        #

        # Test Base Stack with no initialization
        hstack = HierarchicalStack()

        self.assertEqual(hstack.getSize(level=-1), 0)
        self.assertEqual(hstack.getSize(level=0), 0)
        self.assertEqual(hstack.getSize(level=1), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 1)
        self.assertEqual(hstack.isEmpty(level=0), 1)
        self.assertEqual(hstack.isEmpty(level=1), 1)

        self.assertEqual(hstack.isFull(level=-1), 0)
        self.assertEqual(hstack.isFull(level=0), 0)
        self.assertEqual(hstack.isFull(level=1), 0)


        # Adding one element at level 0
        hstack.push('elt1', level=0)

        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.getSize(level=0), 1)

        self.assertEqual(hstack.getSize(level=1), 0)
        self.assertEqual(hstack.getSize(level=-1), 0)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 1)
        self.assertEqual(hstack.isEmpty(level=1), 1)

        self.assertEqual(hstack.isFull(), 0)
        self.assertEqual(hstack.isFull(level=0), 0)

        self.assertEqual(hstack.isFull(level=-1), 0)
        self.assertEqual(hstack.isFull(level=1), 0)

        # Adding one element at level -1
        hstack.push('elt-1', level=-1)

        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.getSize(level=0), 1)

        self.assertEqual(hstack.getSize(level=1), 0)
        self.assertEqual(hstack.getSize(level=-1), 1)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 1)

        self.assertEqual(hstack.isFull(), 0)
        self.assertEqual(hstack.isFull(level=0), 0)

        self.assertEqual(hstack.isFull(level=-1), 0)
        self.assertEqual(hstack.isFull(level=1), 0)

        # Adding one element at level 1
        hstack.push('elt11', level=1)

        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.getSize(level=0), 1)

        self.assertEqual(hstack.getSize(level=1), 1)
        self.assertEqual(hstack.getSize(level=-1), 1)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 0)

        self.assertEqual(hstack.isFull(), 0)
        self.assertEqual(hstack.isFull(level=0), 0)

        self.assertEqual(hstack.isFull(level=-1), 0)
        self.assertEqual(hstack.isFull(level=1), 0)

        # Adding same element at each level  (Not allowed with this stack)

        # Level 0
        res = hstack.push('elt1', level=0)
        self.assertEqual(res, -2)

        res = hstack.push('elt-1', level=0)
        self.assertEqual(res, 1)

        res = hstack.push('elt11', level=0)
        self.assertEqual(res, 1)

        # Level -1
        res = hstack.push('elt-1', level=-1)
        self.assertEqual(res, -2)

        res = hstack.push('elt1', level=-1)
        self.assertEqual(res, 1)

        res = hstack.push('elt11', level=-1)
        self.assertEqual(res, 1)

        # Level 1
        res = hstack.push('elt11', level=1)
        self.assertEqual(res, -2)

        res = hstack.push('elt-1', level=1)
        self.assertEqual(res, 1)

        res = hstack.push('elt1', level=1)
        self.assertEqual(res, 1)

        self.assertEqual(hstack.getSize(), 3)
        self.assertEqual(hstack.getSize(level=0), 3)
        self.assertEqual(hstack.getSize(level=-1), 3)
        self.assertEqual(hstack.getSize(level=1), 3)

        # Check level 0 (current level)
        self.assertEqual(hstack.getLevelContent(), ['elt1','elt-1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=0), ['elt1','elt-1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=-1), ['elt-1','elt1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=1), ['elt11','elt-1','elt1'])

        # Dec Level
        clevel = hstack.doDecLevel()
        self.assertEqual(clevel, -1)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Check the level content
        self.assertEqual(hstack.getLevelContent(),
                         hstack.getLevelContent(level=hstack.getCurrentLevel()))
        self.assertEqual(hstack.getLevelContent(),
                         hstack.getLevelContent(level=-1))
        self.assertEqual(hstack.getLevelContent(),
                         ['elt-1','elt1','elt11'])

        # Check the consistency of the rest
        self.assertEqual(hstack.getLevelContent(level=0), ['elt1','elt-1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=-1), ['elt-1','elt1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=1), ['elt11','elt-1','elt1'])

        # Increment now
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, 0)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        self.assertEqual(hstack.getLevelContent(), ['elt1','elt-1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=0), ['elt1','elt-1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=-1), ['elt-1','elt1','elt11'])
        self.assertEqual(hstack.getLevelContent(level=1), ['elt11','elt-1','elt1'])

        # Increment again
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, 1)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Check the level content
        self.assertEqual(hstack.getLevelContent(),
                         hstack.getLevelContent(level=hstack.getCurrentLevel()))
        self.assertEqual(hstack.getLevelContent(),
                         hstack.getLevelContent(level=1))
        self.assertEqual(hstack.getLevelContent(),
                         ['elt11','elt-1','elt1'])

        # Check levels
        self.assertEqual(hstack.getAllLevels(), [-1, 0, 1])

        # Let's test the remove / pop API

        # Pop element at current level (1)
        self.assertEqual(hstack.getCurrentLevel(), 1)
        self.assertEqual(hstack.pop(), 'elt1')

        # Let's check the consistency of the rest
        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.getSize(level=0), 3)

        self.assertEqual(hstack.getSize(level=1), 2)
        self.assertEqual(hstack.getSize(level=-1), 3)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 0)

        # Pop element at level 0
        self.assertEqual(hstack.getCurrentLevel(), 1)
        self.assertEqual(hstack.pop(level=0), 'elt11')

        # Let's check the consistency of the rest
        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.getSize(level=0), 2)

        self.assertEqual(hstack.getSize(level=1), 2)
        self.assertEqual(hstack.getSize(level=-1), 3)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 0)

        # Pop element at level -1
        self.assertEqual(hstack.getCurrentLevel(), 1)
        self.assertEqual(hstack.pop(level=-1), 'elt11')

        # Let's check the consistency of the rest
        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.getSize(level=0), 2)

        self.assertEqual(hstack.getSize(level=1), 2)
        self.assertEqual(hstack.getSize(level=-1), 2)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 0)

        # Let's change level
        clevel = hstack.doDecLevel()
        self.assertEqual(clevel, hstack.getCurrentLevel())
        self.assertEqual(clevel, 0)

        # Let's check the consistency of the rest
        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.getSize(level=0), 2)

        self.assertEqual(hstack.getSize(level=1), 2)
        self.assertEqual(hstack.getSize(level=-1), 2)

        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isEmpty(level=0), 0)

        self.assertEqual(hstack.isEmpty(level=-1), 0)
        self.assertEqual(hstack.isEmpty(level=1), 0)

        # Check now the removeElement
        self.assertEqual(hstack.removeElement(elt='XXX'), -1)
        self.assertEqual(hstack.removeElement(), 0)
        self.assertEqual(hstack.removeElement(level=89), 0)
        self.assertEqual(hstack.removeElement(elt='elt1', level=89), -1)
        self.assertEqual(hstack.removeElement(elt='elt1'), 'elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.getSize(level=hstack.getCurrentLevel()), 1)
        self.assertEqual(hstack.getSize(level=0), 1)
        self.assertEqual(hstack.removeElement(elt='elt1'), -1)
        self.assertEqual(hstack.removeElement(elt='elt-1'), 'elt-1')
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)

        # Check levels
        self.assertEqual(hstack.getAllLevels(), [-1, 1])
        clevel = hstack.doDecLevel()
        self.assertEqual(clevel, -1)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Not possible to go back to level 0 (empty)
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, -1)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Add an elemet to level 0
        self.assertEqual(hstack.push(elt='elt1', level=0), 1)

        # Now possible to go back to level 0
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, 0)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Let's empty evrything
        clevel = hstack.doDecLevel()
        self.assertEqual(clevel, -1)
        self.assertEqual(clevel, hstack.getCurrentLevel())
        self.assertEqual(hstack.pop(), 'elt1')
        self.assertEqual(hstack.pop(), 'elt-1')

        # Empty now (-1)
        self.assertEqual(hstack.pop(), 0)
        self.assertEqual(hstack.isEmpty(), 1)

        # Go back to 0
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, 0)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        # Trying to go back to -1
        clevel = hstack.doDecLevel()
        self.assertEqual(clevel, 0)
        self.assertEqual(clevel, hstack.getCurrentLevel())
        # ... now way... let's pop the level 0

        self.assertEqual(hstack.pop(), 'elt1')
        # Empty now (0)
        self.assertEqual(hstack.pop(), 0)
        self.assertEqual(hstack.isEmpty(), 1)

        # Go to 1
        clevel = hstack.doIncLevel()
        self.assertEqual(clevel, 1)
        self.assertEqual(clevel, hstack.getCurrentLevel())

        self.assertEqual(hstack.pop(), 'elt-1')
        self.assertEqual(hstack.pop(), 'elt11')
        # Empty now (1)
        self.assertEqual(hstack.pop(), 0)
        self.assertEqual(hstack.isEmpty(), 1)

        # Check the status of the stack now
        self.assertEqual(hstack.getAllLevels(), [])
        self.assertEqual(hstack.getLevelContent(), [])
        self.assertEqual(hstack.getLevelContent(level=-1), [])
        self.assertEqual(hstack.getLevelContent(level=0), [])
        self.assertEqual(hstack.getLevelContent(level=1), [])

        # Check wiered stuffs
        self.assertEqual(hstack.getLevelContent(level=90000), [])
        self.assertEqual(hstack.removeElement(level=90000), 0)

    def test_simpleHierarchicalStackWithMaxSize(self):

        #
        # This tests are all done at level 0 implicitly
        # They are the same as the one on the SimpleStack
        # The idea is to show it's possible to use the hierarchical stack
        # as a simple stack without having to care of the current level
        # It's just a validation of the implementation
        #

        # Test Base Stack with no initialization
        hstack = HierarchicalStack(maxsize=2)
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Adding one element
        hstack.push('elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Adding same element. (Not allowed with this stack)
        res = hstack.push('elt1')
        self.assertEqual(res, -2)
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        self.assertEqual(hstack.getStackContent(), {0:['elt1']})

        # Adding another element.
        res = hstack.push('elt2')
        self.assertEqual(res, 1)

        self.assertEqual(hstack.getStackContent(), {0:['elt1','elt2']})

        self.assertEqual(hstack.getSize(), 2)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 1)

        # Pop now
        elt = hstack.pop()
        self.assertEqual(elt, 'elt2')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 0)
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Adding one element
        hstack.push('elt1')
        self.assertEqual(hstack.getSize(), 1)
        self.assertEqual(hstack.isEmpty(), 0)
        self.assertEqual(hstack.isFull(), 0)

        # Pop again
        elt = hstack.pop()
        self.assertEqual(elt, 'elt1')
        self.assertEqual(hstack.getSize(), 0)
        self.assertEqual(hstack.isEmpty(), 1)
        self.assertEqual(hstack.isFull(), 0)

        # Try to push a None element
        res = hstack.push(None)
        self.assertEqual(res, -1)

        hstack = HierarchicalStack()

        # Test the removeElement() method
        self.assertEqual(hstack.getStackContent(), {})
        self.assertEqual(hstack.removeElement('elt1'), -1)
        hstack.push('elt1')
        self.assertEqual(hstack.removeElement('elt1'), 'elt1')
        hstack.push('elt1')
        hstack.push('elt2')
        self.assertEqual(hstack.getStackContent(), {0:['elt1', 'elt2']})
        hstack.push('elt3')
        self.assertEqual(hstack.getStackContent(), {0:['elt1', 'elt2', 'elt3']})
        self.assertEqual(hstack.removeElement('elt2'), 'elt2')
        self.assertEqual(hstack.getStackContent(), {0:['elt1', 'elt3']})

        hstack.removeElement('elt3')
        hstack.removeElement('elt1')
        self.assertEqual(hstack.getStackContent(), {0:[]})

        # direction
        self.assertEqual(hstack.getDirection(), 1)
        self.assertEqual(hstack.blockDirection(), 0)
        self.assertEqual(hstack.getDirection(), 0)
        self.assertEqual(hstack.setDirectionUp(), -1)
        self.assertEqual(hstack.getDirection(), -1)
        self.assertEqual(hstack.blockDirection(), 0)
        self.assertEqual(hstack.getDirection(), 0)
        self.assertEqual(hstack.setDirectionDown(), 1)
        self.assertEqual(hstack.getDirection(), 1)
        self.assertEqual(hstack.returnedUpDirection(), -1)
        self.assertEqual(hstack.returnedUpDirection(), 1)


    def test_SimpleStackCopy(self):
        # Test getCopy()

        sstack1 = SimpleStack()
        self.assertEqual(sstack1.meta_type, 'Simple Stack')
        sstack2 = sstack1.getCopy()
        self.assertEqual(sstack2.meta_type, 'Simple Stack')

        self.assertNotEqual(sstack2, None)
        self.assertNotEqual(sstack1, sstack2)

        self.assertEqual(sstack1.getStackContent(), [])
        self.assertEqual(sstack2.getStackContent(), [])

        self.assertEqual(sstack1.getStackContent(), sstack2.getStackContent())
        self.assertEqual(sstack1.isFull(), sstack2.isFull())
        self.assertEqual(sstack1.isEmpty(), sstack2.isEmpty())
        self.assertEqual(sstack1.getSize(), sstack2.getSize())

        sstack1.push('elt1')
        sstack2.push('elt2')
        self.assertEqual(sstack1.getStackContent(), ['elt1'])
        self.assertEqual(sstack2.getStackContent(), ['elt2'])

        self.assertNotEqual(sstack1.getStackContent(), sstack2.getStackContent())

    def test_HierarchicalStackCopy(self):

        #
        # Test getCopy()
        # Goal is to prove the copy is not same object
        #

        hstack1 = HierarchicalStack()
        self.assertEqual(hstack1.meta_type, 'Hierarchical Stack')
        hstack2 = hstack1.getCopy()
        self.assertEqual(hstack2.meta_type, 'Hierarchical Stack')

        self.assertNotEqual(hstack2, None)
        self.assertNotEqual(hstack1, hstack2)

        self.assertEqual(hstack1.getStackContent(), {})
        self.assertEqual(hstack2.getStackContent(), {})

        self.assertEqual(hstack1.getStackContent(), hstack2.getStackContent())
        self.assertEqual(hstack1.isFull(), hstack2.isFull())
        self.assertEqual(hstack1.isEmpty(), hstack2.isEmpty())
        self.assertEqual(hstack1.getSize(), hstack2.getSize())

        hstack1.push('elt1')
        hstack2.push('elt2')
        self.assertEqual(hstack1.getLevelContent(), ['elt1'])
        self.assertEqual(hstack2.getLevelContent(), ['elt2'])

        self.assertNotEqual(hstack1.getStackContent(), hstack2.getStackContent())

    def test_former_localroles_mapping(self):

        #
        # Test the behavior of the record of the former local role
        # mapping
        #

        base = BaseStack()
        simple = SimpleStack()
        hierarchical = HierarchicalStack()

        self.assertEqual(base.getFormerLocalRolesMapping(), {})
        self.assertEqual(simple.getFormerLocalRolesMapping(), {})
        self.assertEqual(hierarchical.getFormerLocalRolesMapping(), {})

        simple.setFormerLocalRolesMapping({'user1': 'WorkspaceManager'})
        csimple = simple.getCopy()
        self.assertEqual(simple.getFormerLocalRolesMapping(),
                         csimple.getFormerLocalRolesMapping())
        csimple.setFormerLocalRolesMapping({'user2': 'WorkspaceManager'})
        self.assertNotEqual(simple.getFormerLocalRolesMapping(),
                            csimple.getFormerLocalRolesMapping())

        hierarchical.setFormerLocalRolesMapping({'user1': 'WorkspaceManager'})
        chierarchical = hierarchical.getCopy()
        self.assertNotEqual(hierarchical, chierarchical)
        self.assertEqual(hierarchical.getFormerLocalRolesMapping(),
                         chierarchical.getFormerLocalRolesMapping())
        chierarchical.setFormerLocalRolesMapping({'user2': 'WorkspaceManager'})
        self.assertNotEqual(hierarchical.getFormerLocalRolesMapping(),
                            chierarchical.getFormerLocalRolesMapping())

    def test_reset_simple_wf_stack(self):

        #
        # Test the reset API
        #

        simple = SimpleStack()
        self.assertEqual(simple.getMetaType(),
                         'Simple Stack')
        simple.push('elt1')
        self.assertEqual(simple.getStackContent(),
                         ['elt1'])
        simple.reset()
        self.assertEqual(simple.getMetaType(),
                         'Simple Stack')
        self.assertNotEqual(simple.getStackContent(),
                            ['elt1'])
        self.assertEqual(simple.getStackContent(),
                         [])

        simple.push('elt1')
        self.assertEqual(simple.getStackContent(),
                         ['elt1'])

    def test_reset_hierarchical_wf_stack(self):

        #
        # Test the reset API
        #

        hierarchical = HierarchicalStack()
        self.assertEqual(hierarchical.getMetaType(),
                         'Hierarchical Stack')
        self.assertEqual(hierarchical.getStackContent(),
                         {})
        hierarchical.push('elt1')
        self.assertNotEqual(hierarchical.getStackContent(),
                            {})
        self.assertEqual(hierarchical.getLevelContent(),
                         ['elt1'])
        hierarchical.reset()
        self.assertEqual(hierarchical.getStackContent(),
                         {})
        self.assertEqual(hierarchical.getMetaType(),
                         'Hierarchical Stack')
        self.assertNotEqual(hierarchical.getLevelContent(),
                            ['elt1'])
        self.assertEqual(hierarchical.getLevelContent(),
                         [])

        hierarchical.push('elt1')
        self.assertEqual(hierarchical.getLevelContent(),
                         ['elt1'])

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(TestCPSWorkflowStacks)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
