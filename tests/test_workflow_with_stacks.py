#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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
"""Tests for the CPS Workflow Tool and CPS Worflow with stacks

This test case implements a full delegation / validation workflow and covers
the whole stack workflow API.
"""

import os, sys
from types import DictType
if __name__ == '__main__':
    execfile(os.path.join(sys.path[0], 'framework.py'))

from Testing import ZopeTestCase
ZopeTestCase.installProduct('CPSCore')

import Zope
import unittest

from OFS.Folder import Folder
from Products.CMFDefault.Portal import manage_addCMFSite

from Products.CMFCore.utils import getToolByName

from Products.CPSCore.CPSWorkflow import CPSWorkflowDefinition
from Products.CPSCore.CPSWorkflow import TRIGGER_USER_ACTION

from Products.CPSCore.CPSWorkflowConfiguration \
    import addCPSWorkflowConfiguration

from Products.CPSCore.CPSWorkflowTool import CPSWorkflowConfig_id

from Products.CPSCore.CPSWorkflowTransitions import *
from Products.CPSCore.CPSWorkflowStates import *

from Products.CPSCore.CPSWorkflowTransitions import\
     transition_behavior_export_dict as tbdict

from dummy import DummyContent

portal_name = 'portal'

class WorkflowToolTests(ZopeTestCase.PortalTestCase):
    """Test CPS Workflow Tool and CPS Workflow stacks """

    def getPortal(self):
        if not hasattr(self.app, portal_name):
            manage_addCMFSite(self.app,
                              portal_name)
        return self.app[portal_name]

    #####################################################################

    def afterSetUp(self):
        # Set portal
        self.portal = self.getPortal()

        # Set workflow tool
        self.portal.manage_delObjects(['portal_workflow'])
        self.portal.manage_addProduct['CPSCore'].manage_addTool(
            'CPS Workflow Tool')

        self.ttool = getToolByName(self.portal, 'portal_types')
        self.wftool = getToolByName(self.portal, 'portal_workflow')

        # Set workflow definitions that we gonna test
        self._makeWorkflows()

        # Put a folder and an object here
        self._makeTree()

    ####################################################################

    def _makeTree(self):
        f = Folder()
        f.id = 'f'
        self.portal._setObject(f.id, f)
        f = self.portal.f
        dummy = DummyContent('dummy')

        # Set the global workflow chain
        self.wftool.setChainForPortalTypes(('File',), ('wf',))

        # Setup placeful workflows
        addCPSWorkflowConfiguration(f)
        config = getattr(f, CPSWorkflowConfig_id)
        config.setChain('File', ('wf',))

        # Create a dummy File object
        f.invokeFactory('File','dummy')

    ######################################################################

    def _makeWorkflows(self):

        #
        # WORKFLOW DEFINITION
        #

        wftool = self.wftool

        id = 'wf'
        wf = CPSWorkflowDefinition(id)

        if id in wftool.objectIds():
            wftool._delObjects([id])

        wftool._setObject(id, wf)
        wf = wftool.wf

        #
        # STACKS
        #

        pilots = HierarchicalWorkflowStackDefinition(
            DATA_STRUCT_STACK_TYPE_HIERARCHICAL,
            'Pilots',
            ass_local_role='WorkspaceManager',
            up_ass_local_role='WorkspaceReader',
            down_ass_local_role='WorkspaceMember',
            # the pilots stack can manage the Associates and Observers stacks
            manager_stack_ids=['Associates', 'Observers'])
        associates = SimpleWorkflowStackDefinition(
            DATA_STRUCT_STACK_TYPE_LIFO,
            'Associates',
            ass_local_role='WorkspaceMember',
            manager_stack_ids=['Pilots',])
        observers = SimpleWorkflowStackDefinition(
            DATA_STRUCT_STACK_TYPE_LIFO,
            'Observers',
            ass_local_role='WorkspaceReader',
            manager_stack_ids=['Pilots',])

        #
        # STATES
        #

        wf.states.addState('delegating')
        wf.states.addState('writing')
        wf.states.addState('validating')
        wf.states.addState('closed')

        wf.states.setInitialState('delegating')

        # Check if they do exist
        states = list(wf.states.objectIds())
        states.sort()
        self.assertEqual(tuple(states), ('closed',
                                         'delegating',
                                         'validating',
                                         'writing',
                                         ))

        ### Check the initial properties
        ##for state in states:
        ##    s = wf.states.get(state)
        ##    self.assertEqual(s.title, '')
        ##    self.assertEqual(s.description, '')
        ##    self.assertEqual(s.transitions, ())
        ##    self.assertEqual(s.state_behaviors, ())
        ##    self.assertEqual(s.state_delegatees_vars_info, {})
        ##    self.assertEqual(s.push_on_workflow_variable, [])
        ##    self.assertEqual(s.pop_on_workflow_variable, [])
        ##    self.assertEqual(s.returned_up_hierarchy_on_workflow_variable, [])
        ##    self.assertEqual(s.workflow_up_on_workflow_variable,  [])
        ##    self.assertEqual(s.workflow_down_on_workflow_variable, [])
        ##    self.assertEqual(s.workflow_lock_on_workflow_variable, [])
        ##    self.assertEqual(s.workflow_unlock_on_workflow_variable, [])
        ##    self.assertEqual(s.workflow_reset_on_workflow_variable, [])


        # Set workflow stacks to states
        for state in states:
            s = wf.states.get(state)
            for id, stack in (('pilots',pilots),
                              ('associates', associates),
                              ('observers', observers)
                              ):
                s.state_delegatees_vars_info[id] = stack

        # Test stack fixture
        for state in states:
            s = wf.states.get(state)
            stackdefs = s.getDelegateesVarsInfo()
            self.assertNotEqual(stackdefs,
                                {})
            self.assert_(len(stackdefs.keys()) == 3)

            for id, stack in (('pilots',pilots),
                              ('associates', associates),
                              ('observers', observers)
                              ):
                self.assert_(stackdefs[id] == stack)

        # Add behaviors to states
        s = wf.states.get('delegating')
        s.setProperties(
            title='Delegating',
            description='Delegating',
            state_behaviors = (STATE_BEHAVIOR_PUSH_DELEGATEES,
                               STATE_BEHAVIOR_POP_DELEGATEES,
                               STATE_BEHAVIOR_WORKFLOW_UP,
                               STATE_BEHAVIOR_WORKFLOW_LOCK,
                               STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                               STATE_BEHAVIOR_WORKFLOW_RESET,),
            push_on_workflow_variable = ['Pilots', 'Associates', 'Observers'],
            pop_on_workflow_variable = ['Pilots', 'Associates', 'Observers'],
            workflow_up_on_workflow_variable = ['Pilots'],
            workflow_lock_on_workflow_variable = ['Pilots', 'Associates',
                                                  'Observers'],
            workflow_unlock_on_workflow_variable = ['Pilots', 'Associates',
                                                    'Observers'],
            workflow_reset_on_workflow_variable = ['Pilots', 'Associates',
                                                   'Observers'],)

        s = wf.states.get('writing')
        s.setProperties(
            title='Writing',
            description='Writing',
            state_behaviors = (STATE_BEHAVIOR_WORKFLOW_LOCK,
                               STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                               STATE_BEHAVIOR_RETURNED_UP_HIERARCHY,
                               STATE_BEHAVIOR_WORKFLOW_RESET,),
            workflow_lock_on_workflow_variable = ['Pilots', 'Associates',
                                                  'Observers'],
            workflow_unlock_on_workflow_variable = ['Pilots', 'Associates',
                                                    'Observers'],
            returned_up_hierarchy_on_workflow_variable = ['Pilots'],
            workflow_reset_on_workflow_variable = ['Pilots', 'Associates',
                                                   'Observers'],)


        s = wf.states.get('validating')
        s.setProperties(
            title='Validating',
            description='Validating',
            state_behaviors = (STATE_BEHAVIOR_PUSH_DELEGATEES,
                               STATE_BEHAVIOR_POP_DELEGATEES,
                               STATE_BEHAVIOR_WORKFLOW_DOWN,
                               STATE_BEHAVIOR_WORKFLOW_LOCK,
                               STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                               STATE_BEHAVIOR_WORKFLOW_RESET,),
            push_on_workflow_variable = ['Pilots'],
            pop_on_workflow_variable = ['Pilots'],
            workflow_down_on_workflow_variable = ['Pilots'],
            workflow_lock_on_workflow_variable = ['Pilots', 'Associates',
                                                  'Observers'],
            workflow_unlock_on_workflow_variable = ['Pilots', 'Associates',
                                                    'Observers'],
            workflow_reset_on_workflow_variable = ['Pilots', 'Associates',
                                                   'Observers'],)

        s = wf.states.get('closed')
        s.setProperties(
            title='Closed',
            description='Closed',
            state_behaviors = (STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                               STATE_BEHAVIOR_WORKFLOW_RESET,),
            workflow_unlock_on_workflow_variable = ['Pilots', 'Associates',
                                                    'Observers'],
            workflow_reset_on_workflow_variable = ['Pilots', 'Associates',
                                                   'Observers'],)

        # Test stack defs after property changed
        for state in states:
            s = wf.states.get(state)
            stackdefs = s.getDelegateesVarsInfo()
            self.assertNotEqual(stackdefs,
                                {})
            self.assert_(len(stackdefs.keys()) == 3)

            for id, stack in (('pilots',pilots),
                              ('associates', associates),
                              ('observers', observers)
                              ):
                self.assert_(stackdefs[id] == stack)

        #
        # TRANSITIONS
        #

        # Initial transition
        wf.transitions.addTransition('create')
        t = wf.transitions.get('create')
        t.setProperties('title',
                        'create',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=(tbdict[TRANSITION_INITIAL_CREATE],
                                             ))

        # Delegate
        wf.transitions.addTransition('delegate')
        t = wf.transitions.get('delegate')
        t.setProperties('title',
                        'delegate',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=('behavior_push_delegatees',
                                             'behavior_pop_delegatees',
                                             'behavior_workflow_up',
                                             'behavior_workflow_lock',
                                             'behavior_workflow_unlock',
                                             'behavior_workflow_reset'))

        # to_writing
        wf.transitions.addTransition('to_writing')
        t = wf.transitions.get('to_writing')
        t.setProperties('title',
                        'to_writing',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=())

        # Validate
        wf.transitions.addTransition('validate')
        t = wf.transitions.get('validate')
        t.setProperties('title',
                        'delegate',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=('behavior_push_delegatees',
                                             'behavior_pop_delegatees',
                                             'behavior_workflow_down',
                                             'behavior_workflow_lock',
                                             'behavior_workflow_unlock',
                                             'behavior_workflow_reset'))

        # to_validate
        wf.transitions.addTransition('to_validate')
        t = wf.transitions.get('to_validate')
        t.setProperties('title',
                        'to_validate',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=(
            'behavior_workflow_lock',
            'behavior_workflow_unlock',
            'behavior_return_up_delegatees_hierarchy',
            'behavior_workflow_reset'))

        # Close
        wf.transitions.addTransition('close')
        t = wf.transitions.get('close')
        t.setProperties('title',
                        'close',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=('behavior_workflow_unlock'))


        # Check if they do exist
        transitions = wf.transitions.objectIds()
        transitions.sort()
        self.assertEqual(tuple(transitions), ('close',
                                              'create',
                                              'delegate',
                                              'to_validate',
                                              'to_writing',
                                              'validate',
                                              ))

        #
        # Variables
        #

        for v in ('action',
                  'actor',
                  'comments',
                  'review_history',
                  'time',
                  'dest_container',
                  ):
            wf.variables.addVariable(v)

        vdef = wf.variables['action']
        vdef.setProperties(description='The last transition',
                           default_expr='transition/getId|nothing',
                           for_status=1, update_always=1)

        vdef = wf.variables['actor']
        vdef.setProperties(description='The ID of the user who performed '
                           'the last transition',
                           default_expr='user/getId',
                           for_status=1, update_always=1)

        vdef = wf.variables['comments']
        vdef.setProperties(description='Comments about the last transition',
                           default_expr="python:state_change.kwargs.get('comment',\
                           '')",
                           for_status=1, update_always=1)

        vdef = wf.variables['review_history']
        vdef.setProperties(description='Provides access to workflow history',
                           default_expr="state_change/getHistory",
                           props={'guard_permissions':'',
                                  'guard_roles':'Manager; WorkspaceManager; \
                                  WorkspaceMember; WorkspaceReader; Member',
                                  'guard_expr':''})

        vdef = wf.variables['time']
        vdef.setProperties(description='Time of the last transition',
                           default_expr="state_change/getDateTime",
                           for_status=1, update_always=1)

        vdef = wf.variables['dest_container']
        vdef.setProperties(description='Destination container for the last \
        paste/publish',
                           default_expr="python:state_change.kwargs.get(\
                           'dest_container', '')",
                           for_status=1, update_always=1)

        wf.variables.setStateVar('review_state')

        #
        # Workflow for the container
        #

        id2 = 'wf2'
        wf2 = CPSWorkflowDefinition(id2)
        wftool._setObject(id2, wf2)

        # A a state
        wf2.states.addState('work')
        s = wf2.states.get('work')
        s.transitions = ('create',)

        # Initial transition
        wf2.transitions.addTransition('create')
        t = wf2.transitions.get('create')
        t.setProperties('title',
                        'create',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=(tbdict[TRANSITION_INITIAL_CREATE],
                                             ))

        # Allow sub-content creation
        wf2.transitions.addTransition('create_content')
        t = wf2.transitions.get('create_content')
        t.setProperties('title',
                        'create',
                        trigger_type=TRIGGER_USER_ACTION,
                        transition_behavior=(tbdict[TRANSITION_ALLOWSUB_CREATE],
                                             ))
    ###################################################################
    # TESTS STARTS HERE
    ###################################################################

    def test_wftool_api_at_initialization(self):

        #
        # TEST WORKFLOW TOOL API RELATED TO WORKFLOW STACKS
        #

        wftool = self.wftool

        content = getattr(self.portal.f, 'dummy')

        # Test content / wftool fixtures
        self.assertEqual(wftool.getChainFor(content), ('wf',))
        self.assertEqual(len(wftool.getWorkflowsFor(content)),  1)
        self.assertEqual(wftool.getInfoFor(content, 'review_state'),
                         'delegating')

        #
        #  def getStackDefinitionsFor(self, ob)
        #

        stackdefs = wftool.getStackDefinitionsFor(content)

        # Test returned structure
        self.assert_(isinstance(stackdefs, DictType))
        self.assertNotEqual(stackdefs, {})

        # Test fixtures of stackdefs
        keys = stackdefs.keys()
        keys.sort()
        self.assert_(len(keys) == 3)
        self.assertEqual(keys, ['associates', 'observers', 'pilots'])
        self.assert_(isinstance(stackdefs['associates'],
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(stackdefs['observers'],
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(stackdefs['pilots'],
                                HierarchicalWorkflowStackDefinition))
        self.assertNotEqual(stackdefs['associates'], None)
        self.assertNotEqual(stackdefs['observers'], None)
        self.assertNotEqual(stackdefs['pilots'], None)

        #
        # getStackDefinitionFor(self, ob, wf_var_id='')
        #

        assos = wftool.getStackDefinitionFor(content, 'associates')
        obs = wftool.getStackDefinitionFor(content, 'observers')
        pilots = wftool.getStackDefinitionFor(content, 'pilots')

        self.assert_(isinstance(assos,
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(obs,
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(pilots,
                                HierarchicalWorkflowStackDefinition))
        self.assertNotEqual(assos, None)
        self.assertNotEqual(obs, None)
        self.assertNotEqual(pilots, None)

        # Test consistency
        self.assertEqual( wftool.getStackDefinitionFor(content, 'associates'),
                          wftool.getStackDefinitionsFor(content)['associates'])
        self.assertEqual( wftool.getStackDefinitionFor(content, 'observers'),
                          wftool.getStackDefinitionsFor(content)['observers'])
        self.assertEqual( wftool.getStackDefinitionFor(content, 'pilots'),
                          wftool.getStackDefinitionsFor(content)['pilots'])

        # Stack doesn't exist

        self.assertEqual(wftool.getStackDefinitionFor(content), None)
        self.assertEqual(wftool.getStackDefinitionFor(content, 'Pas bien'), None)

        #
        # getDelegateesDataStructures(self, ob)
        # Note the status is not yet set for stacks
        #

        ds = wftool.getDelegateesDataStructures(content)
        self.assert_(isinstance(ds, DictType))
        keys = ds.keys()
        keys.sort()
        self.assert_(len(keys) == 3)
        self.assertEqual(keys, ['associates', 'observers', 'pilots'])

        for v in ds.values():
            self.assertEqual(v, None)

        #
        # def getDelegateesDataStructureFor(self, ob, stack_id)
        #

        ds_assos = wftool.getDelegateesDataStructureFor(content, 'associates')
        ds_obs = wftool.getDelegateesDataStructureFor(content, 'observers')
        ds_pilots = wftool.getDelegateesDataStructureFor(content, 'pilots')

        self.assertEqual(ds_assos, None)
        self.assertEqual(ds_obs, None)
        self.assertEqual(ds_pilots, None)

        # concistency
        self.assertEqual(wftool.getDelegateesDataStructureFor(content, 'associates'),
                         wftool.getDelegateesDataStructures(content)['associates'])
        self.assertEqual(wftool.getDelegateesDataStructureFor(content, 'observers'),
                         wftool.getDelegateesDataStructures(content)['observers'])

    def test_current_state(self):

        #
        # Here, let's check the current state props
        #

        wftool = self.wftool
        content = getattr(self.portal.f, 'dummy')

        self.assertEqual(wftool.getInfoFor(content, 'review_state'), 'delegating')

        # Check current state fixtures
        wf = wftool['wf']
        current_state = wf._getWorkflowStateOf(content)
        self.assertEqual(current_state.getId(), 'delegating')

        # Check stackdefs
        stackdefs = current_state.getDelegateesVarsInfo()
        keys = stackdefs.keys()
        keys.sort()
        self.assert_(isinstance(stackdefs, DictType))
        self.assertEqual(keys, ['associates', 'observers', 'pilots'])
        self.assert_(isinstance(stackdefs['associates'],
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(stackdefs['observers'],
                                SimpleWorkflowStackDefinition))
        self.assert_(isinstance(stackdefs['pilots'],
                                HierarchicalWorkflowStackDefinition))

        # Check consistency
        self.assertEqual(current_state.getDelegateesVarInfoFor('associates'),
                         stackdefs['associates'])
        self.assertEqual(current_state.getDelegateesVarInfoFor('observers'),
                         stackdefs['observers'])
        self.assertEqual(current_state.getDelegateesVarInfoFor('pilots'),
                         stackdefs['pilots'])

        # Check behaviors given this workflow definition
        behaviors = current_state.state_behaviors
        self.assertEqual(behaviors, (STATE_BEHAVIOR_PUSH_DELEGATEES,
                                     STATE_BEHAVIOR_POP_DELEGATEES,
                                     STATE_BEHAVIOR_WORKFLOW_UP,
                                     STATE_BEHAVIOR_WORKFLOW_LOCK,
                                     STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                                     STATE_BEHAVIOR_WORKFLOW_RESET,))
        self.assertEqual(current_state.push_on_workflow_variable,
                         ['Pilots', 'Associates', 'Observers'])
        self.assertEqual(current_state.pop_on_workflow_variable,
                         ['Pilots', 'Associates', 'Observers'])
        self.assertEqual(current_state.workflow_up_on_workflow_variable,
                         ['Pilots'])
        self.assertEqual(current_state.workflow_lock_on_workflow_variable,
                         ['Pilots', 'Associates','Observers'])
        self.assertEqual(current_state.workflow_unlock_on_workflow_variable,
                        ['Pilots', 'Associates', 'Observers'])
        self.assertEqual(current_state.workflow_reset_on_workflow_variable,
                         ['Pilots', 'Associates', 'Observers'],)

        #
        # Test possible transitions
        #

        allowed_transitions = current_state.getTransitions()
        # Not yet initialized
        self.assertEqual(allowed_transitions, ())


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(WorkflowToolTests))
    return suite

if __name__ == '__main__':
    framework()
