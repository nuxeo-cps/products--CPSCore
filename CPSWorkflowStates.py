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

"""CPS Workflow States

Extends DCWorkflow States and DCWorkflow State Definitions.

It adds :
  - Advanced properties management for delegatees.
  - State bahaviors
"""

from zLOG import LOG, ERROR, DEBUG

from Globals import DTMLFile

from Products.DCWorkflow.States import StateDefinition as DCWFStateDefinition
from Products.DCWorkflow.States import States as DCWFStates

from Products.CPSCore.CPSWorkflowStackDefinitions import \
     SimpleWorkflowStackDefinition, \
     HierarchicalWorkflowStackDefinition

from Products.CPSCore.CPSWorkflowStacks import DATA_STRUCT_STACK_TYPE_LIFO, \
     DATA_STRUCT_STACK_TYPE_HIERARCHICAL, data_struct_types_export_dict

#
# State behaviors Use for workflow stacks right now.  It permits to allow a
# behavior on the state. You might have shared transitions doing the same job
# on several states.
#

STATE_BEHAVIOR_PUSH_DELEGATEES = 101
STATE_BEHAVIOR_POP_DELEGATEES = 102
STATE_BEHAVIOR_WORKFLOW_UP = 103
STATE_BEHAVIOR_WORKFLOW_DOWN = 104
STATE_BEHAVIOR_RETURNED_UP_HIERARCHY = 105
STATE_BEHAVIOR_WORKFLOW_LOCK = 106
STATE_BEHAVIOR_WORKFLOW_UNLOCK = 107
STATE_BEHAVIOR_WORKFLOW_RESET = 108

state_behavior_export_dict = {
    STATE_BEHAVIOR_PUSH_DELEGATEES : 'Push Delegatees',
    STATE_BEHAVIOR_POP_DELEGATEES  : 'Pop Delegatees',
    STATE_BEHAVIOR_WORKFLOW_UP     : 'Workflow Up',
    STATE_BEHAVIOR_WORKFLOW_DOWN   : 'Workflow Down',
    STATE_BEHAVIOR_RETURNED_UP_HIERARCHY  : 'Return up hierarchy',
    STATE_BEHAVIOR_WORKFLOW_LOCK     : 'Workflow Lock',
    STATE_BEHAVIOR_WORKFLOW_UNLOCK   : 'Workflow UnLock',
    STATE_BEHAVIOR_WORKFLOW_RESET : 'Workflow Reset',
    }

class CPSStateDefinition(DCWFStateDefinition):
    """ CPS State Definition
    """

    meta_type = 'CPS Workflow State'

    manage_options = (
        DCWFStateDefinition.manage_options[0],
        {'label': 'Workflow Stacks',
         'action': 'manage_advanced_properties'},
        ) + DCWFStateDefinition.manage_options[1:]

    _properties_form = DTMLFile(
        'zmi/workflow_state_properties',
        globals())

    _advanced_properties_form = DTMLFile(
        'zmi/workflow_state_advanced_properties',
        globals())

    state_behaviors = ()
    state_delegatees_vars_info = {}

    # State Behaviors depend on a workflow variables
    push_on_workflow_variable = []
    pop_on_workflow_variable = []
    returned_up_hierarchy_on_workflow_variable = []
    workflow_up_on_workflow_variable = []
    workflow_down_on_workflow_variable = []
    workflow_lock_on_workflow_variable = []
    workflow_unlock_on_workflow_variable = []
    workflow_reset_on_workflow_variable = []

    def setProperties(self,
                      title='',
                      transitions=(),
                      state_behaviors=(),
                      state_delegatees_vars_info={},
                      push_on_workflow_variable = None,
                      pop_on_workflow_variable = None,
                      returned_up_hierarchy_on_workflow_variable = None,
                      workflow_up_on_workflow_variable = None,
                      workflow_down_on_workflow_variable = None,
                      workflow_lock_on_workflow_variable = None,
                      workflow_unlock_on_workflow_variable = None,
                      workflow_reset_on_workflow_variable = None,
                      REQUEST=None,
                      description=''):
        """Set state properties

        DCWorkflow properties / CPS extensions
        """

        self.title = str(title)
        self.description = str(description)
        self.transitions = tuple(map(str, transitions))
        self.state_behaviors = tuple(state_behaviors)

        #
        # Simple edit properties form with no delegatees specified
        # Avoid removing the configuration for delegatees if not
        # specified
        #

        if state_delegatees_vars_info:
            self.state_delegatees_vars_info = dict(state_delegatees_vars_info)

        # Stack workflow state behavior flags
        if push_on_workflow_variable is not None:
            self.push_on_workflow_variable = push_on_workflow_variable
        if pop_on_workflow_variable is not None:
            self.pop_on_workflow_variable = pop_on_workflow_variable
        if returned_up_hierarchy_on_workflow_variable is not None:
            self.returned_up_hierarchy_on_workflow_variable = \
                 returned_up_hierarchy_on_workflow_variable
        if workflow_up_on_workflow_variable is not None:
            self.workflow_up_on_workflow_variable = \
                 workflow_up_on_workflow_variable
        if workflow_down_on_workflow_variable is not None:
            self.workflow_down_on_workflow_variable = \
                 workflow_down_on_workflow_variable
        if workflow_lock_on_workflow_variable is not None:
            self.workflow_lock_on_workflow_variable = \
                 workflow_lock_on_workflow_variable
        if workflow_unlock_on_workflow_variable is not None:
            self.workflow_unlock_on_workflow_variable = \
                 workflow_unlock_on_workflow_variable
        if workflow_reset_on_workflow_variable is not None:
            self.workflow_reset_on_workflow_variable = \
                 workflow_reset_on_workflow_variable

        if REQUEST is not None:
            return self.manage_properties(REQUEST, 'Properties changed.')

    def manage_advanced_properties(self,  REQUEST, manage_tabs_message=None):
        """
        """
        return self._advanced_properties_form(
            REQUEST,
            management_view='Advanced Properties',
            manage_tabs_message=manage_tabs_message,)

    def setDelegateesVarsInfo(self, key, variable_information):
        """Update the variable holding delegate workflow variables information

        key is the workflow variable id which is gonna be used as identifier in
        here.  variable_information is a tuple containing information about
        this variable state side (i.e : Data strucuture / associated local
        roles)

        We will create an instance of CPSWorkflowStackDefinition corresponding
        to the stack workflow type. It will be cleaner since the CPSWorkflow
        after will be able to call the CPSWorkflowStackDefinition from the
        _executeTransition()
        """
        self._p_changed = 1

        stackdef = None

        #
        # Let's check the data structure type and the create a workflow stack
        # definition mapping this ds type
        #

        kw = {}
        kw['ass_local_role'] = variable_information[1]
        kw['up_ass_local_role'] = variable_information[2]
        kw['down_ass_local_role'] = variable_information[3]
        kw['manager_stack_ids'] = variable_information[4]

        if variable_information[0] == DATA_STRUCT_STACK_TYPE_LIFO:
            stackdef = SimpleWorkflowStackDefinition(variable_information[0],
                                                     key,
                                                     **kw)
        if variable_information[0] == DATA_STRUCT_STACK_TYPE_HIERARCHICAL:
            stackdef = HierarchicalWorkflowStackDefinition(
                variable_information[0],
                key,
                **kw)

        #
        # state_delegatees_var_info is a dictionnary with the workflow variable
        # id as key and an instance of stack definition as value
        #

        if stackdef is not None:
            info_dict = self.getDelegateesVarsInfo()
            info_dict[key] = stackdef
            self.state_delegatees_vars_info = info_dict
        else:
            raise NotImplementedError

    def addDelegateesWorkflowVariableInfo(self,
                                          data_struct_type,
                                          var_id='',
                                          ass_local_role='',
                                          up_ass_local_role='',
                                          down_ass_local_role='',
                                          manager_stack_ids=[],
                                          REQUEST=None):
        """Add a new workflow variables hodling the stack where the delegatees
        will be stored

        data_struct_type : stack type (cf. above for the differrent
                               available types
        var_id : workflow variable id used to store this new
                              variable

        ass_local_role : local role given to the people in this stack.

        up_ass_local_role : local role given to the people above the current
        level
        down_ass_local_role : local role givne to the people below the
        current level
        """

        self._p_changed = 1

        workflow = self.getWorkflow()

        # www checks
        if not var_id:
            if REQUEST is not None:
                return self.manage_advanced_properties(
                    REQUEST,
                    'You need to specify a variable id')
            return -1
        if not 'ass_local_role':
            if REQUEST is not None:
                return self.manage_advanced_properties(
                    REQUEST,
                    'Please, specify an associated local roles for this stack')
            return -1

        # Add a workflow variable with new_stack_id as id
        if var_id not in workflow.variables.keys():
            var = workflow.variables.addVariable(var_id)
            var = workflow.variables.get(var_id)
            var.setProperties(
                description="Delegatees variable",
                default_expr="python:state_change.getDelegateesVarInfoFor(var_id='%s')" %var_id,
                for_status=1,
                update_always=0)
        else:
            if REQUEST is not None:
                return self.manage_advanced_properties(
                    REQUEST,
                    'The id you choose is already taken !')
            return -1

        self.setDelegateesVarsInfo(var_id,
                                   (data_struct_type,
                                    ass_local_role,
                                    up_ass_local_role,
                                    down_ass_local_role,
                                    manager_stack_ids))

        if REQUEST is not None:
            return self.manage_advanced_properties(
                REQUEST,
                'New workflow variable defined')

    def delDelegateesWorkflowVariablesInfo(self, ids=[], REQUEST=None):
        """Remove delegatees variables given the id of the variable wich is
        unique
        """

        self._p_changed = 1

        for id in ids:
            if self.getDelegateesVarsInfo().has_key(id):
                # Remove variable from the workflow variable
                workflow = self.getWorkflow()
                try:
                    workflow.variables.deleteVariables([id])
                except KeyError:
                    # The variable has been already removed directly
                    pass
                # Remove the information defined on this state
                del self.state_delegatees_vars_info[id]

        if REQUEST is not None:
            return self.manage_advanced_properties(
                REQUEST,
                'Delegate workflow variables removed !')

    def getAvailableStateBehaviors(self):
        """Get the possible bahavior for the state
        """
        return state_behavior_export_dict

    def getAvailableDataStructureTypes(self):
        """Get the different stack workflow implementations
        """
        return data_struct_types_export_dict

    def getDelegateesVarsInfo(self):
        """Returns the variable information related to delegatees
        """
        return self.state_delegatees_vars_info

    ##############################################################
    ##############################################################

    def getDelegateesVarInfoFor(self, var_id):
        """Return the var info given the var_id
        """
        return self.getDelegateesVarsInfo().get(var_id)

class CPSStates(DCWFStates):
    meta_type = 'CPS Workflow States'

    all_meta_types = ({'name':CPSStateDefinition.meta_type,
                       'action':'addState',
                       },)

    def addState(self, id, REQUEST=None):
        """Add a new state to the workflow."""
        sdef = CPSStateDefinition(id)
        self._setObject(id, sdef)
        if REQUEST is not None:
            return self.manage_main(REQUEST, 'State added.')
