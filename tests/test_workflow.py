#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
# Author: Florent Guillaume <fg@nuxeo.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id$
"""Tests for the CPS Workflow Tool.
"""

import os, sys
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase
ZopeTestCase.installProduct('CPSCore')

import Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder

from Products.CPSCore.CPSWorkflow import CPSWorkflowDefinition
from Products.CPSCore.CPSWorkflow import TRIGGER_USER_ACTION
from Products.CPSCore.CPSWorkflowConfiguration \
    import addCPSWorkflowConfiguration
from Products.CPSCore.CPSWorkflowTool import CPSWorkflowConfig_id

from dummy import DummyContent, DummyTypesTool


class WorkflowToolTests(SecurityRequestTest):
    """Test CPS Workflow Tool."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = Folder()
        self.root.id = 'root'
        root = self.root

        from Products.CMFCore.WorkflowTool import addWorkflowFactory
        addWorkflowFactory(CPSWorkflowDefinition, id='cps wfdef')

        from Products.CPSCore.CPSWorkflowTool import addCPSWorkflowTool
        addCPSWorkflowTool(root)

    def tearDown(self):
        from Products.CMFCore.WorkflowTool import _removeWorkflowFactory
        _removeWorkflowFactory(CPSWorkflowDefinition, id='cps wfdef')

        SecurityRequestTest.tearDown(self)

    ##########

    def makeWorkflows(self):
        id = 'wf'
        wf = CPSWorkflowDefinition(id)
        self.root.portal_workflow._setObject(id, wf)
        wf = self.root.portal_workflow.wf
        #ct = wf.getCreationTransitions(self.root)
        #self.assertEqual(tuple(ct), ())

        # Create states
        wf.states.addState('s1')
        states = list(wf.states.objectIds())
        states.sort()
        self.assertEqual(tuple(states), ('s1',))

        # Create transition
        wf.transitions.addTransition('t1')
        t1 = wf.transitions.get('t1')
        t1.setProperties('title', 's1', trigger_type=TRIGGER_USER_ACTION,
            transition_behavior=('initial_create',))
        transitions = wf.transitions.objectIds()
        self.assertEqual(tuple(transitions), ('t1',))

        # Another empty workflow
        id2 = 'wf2'
        wf2 = CPSWorkflowDefinition(id2)
        self.root.portal_workflow._setObject(id2, wf2)

    def makeTypes(self):
        self.root._setObject('portal_types', DummyTypesTool())

    def makeTree(self):
        f = Folder()
        f.id = 'f'
        self.root._setObject(f.id, f)
        f = self.root.f
        dummy = DummyContent('dummy')
        f._setObject(dummy.getId(), dummy)

    ##########

    def test_wf_getCreationTransitions(self):
        self.makeWorkflows()
        ct = self.root.portal_workflow.wf.getInitialTransitions(
            'Dummy Content', 'initial_create')
        self.assertEqual(tuple(ct), ('t1',))

    def test_wft_getCreationTransitions(self):
        self.makeWorkflows()
        self.makeTypes()
        wft = self.root.portal_workflow
        wft.setChainForPortalTypes(('Dummy Content',), ('wf',))

        # Setup container
        folder = Folder()
        folder.id = 'folder'
        self.root._setObject(folder.id, folder)
        folder = self.root.folder

        # Check default available
        ct = wft.getInitialTransitions(folder, 'Dummy Content', 
            'initial_create')
        self.assertEqual(ct, ['t1'])

    def test_wft_getChainFor(self):
        self.makeWorkflows()
        self.makeTypes()
        self.makeTree()
        wft = self.root.portal_workflow
        f = self.root.f

        # Check default
        chain = wft.getChainFor('Dummy Content', f)
        self.assertEqual(tuple(chain), ())

        # Check global chain
        wft.setChainForPortalTypes(('Dummy Content',), ('wf',))
        chain = wft.getChainFor('Dummy Content', f)
        self.assertEqual(tuple(chain), ('wf',))

        # Check global chain, using object
        dummy = f.dummy
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ('wf',))

        # Remove global chain
        wft.setChainForPortalTypes(('Dummy Content',), ())
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ())

    def test_wft_getChainFor_placeful(self):
        self.makeWorkflows()
        self.makeTypes()
        self.makeTree()
        wft = self.root.portal_workflow
        f = self.root.f
        f2 = Folder()
        f2.id = 'f2'
        f._setObject(f2.id, f2)
        f2 = f.f2

        # Setup placeful workflows
        addCPSWorkflowConfiguration(f)
        config = getattr(f, CPSWorkflowConfig_id)
        config.setChain('Dummy Content', ('wf',))

        # Check placeful
        dummy = f.dummy
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ('wf',))

        # Add new sub folder
        addCPSWorkflowConfiguration(f2)
        config2 = getattr(f2, CPSWorkflowConfig_id)
        config2.setChain('Dummy Content', ('wf2',))

        # Check inheritance order
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf2',))

        # Check empty chain
        config2.setChain('Dummy Content', ())
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ())

        # Check inheritance when no config
        config2.delChain('Dummy Content')
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf',))

        # Check default
        wft.setDefaultChain('wf2')
        config2.setChain('Dummy Content', None)
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf2',))


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(WorkflowToolTests)

#if __name__ == '__main__':
#    unittest.TextTestRunner().run(test_suite())

if __name__ == '__main__':
    framework()

