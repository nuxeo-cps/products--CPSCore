# -*- coding: iso-8859-15 -*-
# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author : Julien Anguenot <ja@nuxeo.com>
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

import Zope
import unittest
from OFS.Folder import Folder

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from Products.CPSCore.CPSWorkflow import CPSWorkflowDefinition
from Products.CPSCore.CPSWorkflow import TRIGGER_USER_ACTION
from Products.CPSCore.CPSWorkflowConfiguration \
    import addCPSWorkflowConfiguration
from Products.CPSCore.CPSWorkflowTool import CPSWorkflowConfig_id

from Products.CPSCore.CPSWorkflowStates import CPSStateDefinition, \
     state_behavior_export_dict
from Products.CPSCore.CPSWorkflowStacks import data_struct_types_export_dict
from Products.CPSCore.CPSWorkflowStacks import BaseStack, SimpleStack, \
     HierarchicalStack

from Products.CPSCore.CPSWorkflowTransitions import CPSTransitionDefinition, \
     CPSTransitions

class TestCPSWorkflowTransitions(SecurityRequestTest):

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

    def test_cps_transition_definition(self):

        #
        # Test the CPS Transition class
        #

        tdef = CPSTransitionDefinition(id='fake')
        tdef.setProperties(title='Transition def title',
                           new_state_id='')
        self.assertRaises(AttributeError, tdef.getAvailableTransitionIds)
        self.assertEqual(tdef.getWorkflow(), None)

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           transition_behavior=(101,),)
        self.assertEqual(tdef.transition_behavior, (101,))

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           transition_behavior=(101,102),)
        self.assertEqual(tdef.transition_behavior, (101,102))

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           transition_behavior=(101,),)
        self.assertEqual(tdef.transition_behavior, (101,))

        # Workflow stack stuffs
        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           push_on_workflow_variable=['xx', 'yy'],)
        self.assertEqual(tdef.push_on_workflow_variable, ['xx', 'yy'])

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           pop_on_workflow_variable=['xx', 'yy'],)
        self.assertEqual(tdef.pop_on_workflow_variable, ['xx', 'yy'])

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           returned_up_hierarchy_on_workflow_variable=['xx', 'yy'],)
        self.assertEqual(tdef.returned_up_hierarchy_on_workflow_variable, ['xx', 'yy'])

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           workflow_up_on_workflow_variable=['xx', 'yy'],)
        self.assertEqual(tdef.workflow_up_on_workflow_variable, ['xx', 'yy'])

        tdef.setProperties(title='Transition def title',
                           new_state_id='',
                           workflow_down_on_workflow_variable=['xx', 'yy'],)
        self.assertEqual(tdef.workflow_down_on_workflow_variable, ['xx', 'yy'])

    def makeWorkflows(self):
        id = 'wf'
        wf = CPSWorkflowDefinition(id)
        self.root.portal_workflow._setObject(id, wf)
        wf = self.root.portal_workflow.wf

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
        return wf

    def test_state_definition_on_workflow(self):
        wf = self.makeWorkflows()
        sdef = wf.transitions.get('t1')

        # more tests

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(TestCPSWorkflowTransitions)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
