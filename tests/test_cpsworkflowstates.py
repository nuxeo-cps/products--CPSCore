# -*- coding: iso-8859-15 -*-
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

class TestCPSWorkflowStates(SecurityRequestTest):

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

    def test_simple_state_definition(self):
        sdef = CPSStateDefinition('sdef')

        self.assertEqual(sdef.getAvailableStateBehaviors(),
                         state_behavior_export_dict)
        self.assertEqual(sdef.getAvailableDataStructureTypes(),
                         data_struct_types_export_dict)

        # Test initial properties
        self.assertEqual(sdef.state_behaviors, ())
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})

        # Just call it without anything
        sdef.setProperties()

        # Test property again
        self.assertEqual(sdef.state_behaviors, ())
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})

        # Test adding state behaviors
        sdef.setProperties(state_behaviors=state_behavior_export_dict.keys())

        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})


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
        sdef = wf.states.get('s1')

        self.assertEqual(sdef.getAvailableStateBehaviors(),
                         state_behavior_export_dict)
        self.assertEqual(sdef.getAvailableDataStructureTypes(),
                         data_struct_types_export_dict)

        # Test initial properties
        self.assertEqual(sdef.state_behaviors, ())
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})

        # Just call it without anything
        sdef.setProperties()

        # Test property again
        self.assertEqual(sdef.state_behaviors, ())
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})

        # Test adding state behaviors
        sdef.setProperties(state_behaviors=state_behavior_export_dict.keys())

        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info, {})

        # Test add delegatees var info
        for ds_type in data_struct_types_export_dict:
            for var_id, lc in (('toto', 'WorkspaceManager'),
                               ('tata', 'WorkspaceMember')):
                sdef.addDelegateesWorkflowVariableInfo(ds_type,
                                                       var_id,
                                                       ass_local_role=lc)
        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())

        dinfo = sdef.getDelegateesVarInfoFor('toto')
        self.assertNotEqual(dinfo, None)
        self.assertEqual(dinfo.getStackDataStructureType(), 201)
        self.assertEqual(dinfo.getStackWorkflowVariableId(), 'toto')
        self.assertEqual(dinfo.getAssociatedLocalRole(), 'WorkspaceManager')

        dinfo = sdef.getDelegateesVarInfoFor('tata')
        self.assertNotEqual(dinfo, None)
        self.assertEqual(dinfo.getStackDataStructureType(), 201)
        self.assertEqual(dinfo.getStackWorkflowVariableId(), 'tata')
        self.assertEqual(dinfo.getAssociatedLocalRole(), 'WorkspaceMember')

        # Let's remove the delegatees var info
        sdef.delDelegateesWorkflowVariablesInfo(['toto'])

        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())

        dinfo = sdef.getDelegateesVarInfoFor('toto')
        self.assertEqual(dinfo, None)

        dinfo = sdef.getDelegateesVarInfoFor('tata')
        self.assertNotEqual(dinfo, None)
        self.assertEqual(dinfo.getStackDataStructureType(), 201)
        self.assertEqual(dinfo.getStackWorkflowVariableId(), 'tata')
        self.assertEqual(dinfo.getAssociatedLocalRole(), 'WorkspaceMember')

        # Let's remove the delegatees var info
        sdef.delDelegateesWorkflowVariablesInfo(['toto'])

        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())

        dinfo = sdef.getDelegateesVarInfoFor('tata')
        self.assertNotEqual(dinfo, None)
        self.assertEqual(dinfo.getStackDataStructureType(), 201)
        self.assertEqual(dinfo.getStackWorkflowVariableId(), 'tata')
        self.assertEqual(dinfo.getAssociatedLocalRole(), 'WorkspaceMember')

        # Let's remove the delegatees var info
        sdef.delDelegateesWorkflowVariablesInfo(['tata'])

        # Test property again
        self.assertEqual(sdef.state_behaviors,
                         tuple(state_behavior_export_dict.keys()))
        self.assertEqual(sdef.transitions, ())
        self.assertEqual(sdef.state_delegatees_vars_info,
                         {})
        self.assertEqual(sdef.getDelegateesVarInfoFor('toto'), None)
        self.assertEqual(sdef.getDelegateesVarInfoFor('tata'), None)
        self.assertEqual(sdef.getDelegateesVarsInfo(), {})

def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(TestCPSWorkflowStates)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
