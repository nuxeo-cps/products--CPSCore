# -*- coding: iso-8859-15 -*-
# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author : Florent Guillaume <fg@nuxeo.com>
# Contributor : Julien Anguenot <ja@nuxeo.com>
#               - CPS Workflow refactoring and cleanup
#               - Workflow stack support
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

"""CPS Workflow Transitions

This modules extends the DCWorkflow based transitions and transitions
definitions.

It currently adds :

 - Transition flags which are here to define an allowed behavior on the
   transition

 - More properties on the TransitionDefinition It's holding the
   configuration. (i.e : transitions flags defined for a given transition and
   associated values. Either transitions or workflow variables)

 - Support for stack workflows. (c.f : doc/StackWorkflows)
"""

from zLOG import LOG, ERROR, DEBUG

from Globals import DTMLFile

from Products.DCWorkflow.Transitions \
     import TransitionDefinition as DCWFTransitionDefinition
from Products.DCWorkflow.Transitions import Transitions as DCWFTransitions
from Products.DCWorkflow.Transitions import TRIGGER_AUTOMATIC
from Products.DCWorkflow.Transitions import TRIGGER_USER_ACTION
from Products.DCWorkflow.Transitions import TRIGGER_WORKFLOW_METHOD

#TRANSITION_BEHAVIOR_SUBCREATE = 1
#TRANSITION_BEHAVIOR_CLONE = 2
#TRANSITION_BEHAVIOR_FREEZE = 3
#TRANSITION_BEHAVIOR_SUBDELETE = 4
#TRANSITION_BEHAVIOR_SUBCOPY = 5
#TRANSITION_BEHAVIOR_CREATION = 6

TRANSITION_ALLOWSUB_CREATE = 10
TRANSITION_ALLOWSUB_DELETE = 11
TRANSITION_ALLOWSUB_MOVE = 12 # Into this container.
TRANSITION_ALLOWSUB_COPY = 13 # Same...
TRANSITION_ALLOWSUB_PUBLISHING = 14
TRANSITION_ALLOWSUB_CHECKOUT = 15

TRANSITION_INITIAL_CREATE = 20
TRANSITION_INITIAL_MOVE = 22
TRANSITION_INITIAL_COPY = 23
TRANSITION_INITIAL_PUBLISHING = 24
TRANSITION_INITIAL_CHECKOUT = 25
TRANSITION_ALLOW_CHECKIN = 26

TRANSITION_BEHAVIOR_DELETE = 31
TRANSITION_BEHAVIOR_MOVE = 32
TRANSITION_BEHAVIOR_COPY = 33
TRANSITION_BEHAVIOR_PUBLISHING = 34
TRANSITION_BEHAVIOR_CHECKOUT = 35
TRANSITION_BEHAVIOR_CHECKIN = 36
TRANSITION_BEHAVIOR_FREEZE = 37
TRANSITION_BEHAVIOR_MERGE = 38

TRANSITION_BEHAVIOR_PUSH_DELEGATEES = 41
TRANSITION_BEHAVIOR_POP_DELEGATEES = 42
TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY = 43
TRANSITION_BEHAVIOR_WORKFLOW_UP = 44
TRANSITION_BEHAVIOR_WORKFLOW_DOWN = 45
TRANSITION_BEHAVIOR_WORKFLOW_LOCK = 46
TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK = 47
TRANSITION_BEHAVIOR_WORKFLOW_RESET = 48

trigger_export_dict = {
    TRIGGER_AUTOMATIC: 'automatic',
    TRIGGER_USER_ACTION: 'user_action',
    TRIGGER_WORKFLOW_METHOD: 'workflow_method',
    }

#trigger_import_dict = {}
#for k,v in trigger_export_dict.items():
#    trigger_import_dict[v] = k

transition_behavior_export_dict = {
    TRANSITION_ALLOWSUB_CREATE: 'allow_sub_create',
    TRANSITION_ALLOWSUB_DELETE: 'allow_sub_delete',
    TRANSITION_ALLOWSUB_MOVE: 'allow_sub_delete',
    TRANSITION_ALLOWSUB_COPY: 'allow_sub_copy',
    TRANSITION_ALLOWSUB_PUBLISHING: 'allow_sub_publishing',
    TRANSITION_ALLOWSUB_CHECKOUT: 'allow_sub_checkout',

    TRANSITION_INITIAL_CREATE: 'initial_create',
    TRANSITION_INITIAL_MOVE: 'initial_move',
    TRANSITION_INITIAL_COPY: 'initial_copy',
    TRANSITION_INITIAL_PUBLISHING: 'initial_clone',
    TRANSITION_INITIAL_CHECKOUT: 'initial_checkout',
    TRANSITION_ALLOW_CHECKIN: 'allow_checkin',

    TRANSITION_BEHAVIOR_DELETE: 'behavior_delete',
    TRANSITION_BEHAVIOR_MOVE: 'behavior_move',
    TRANSITION_BEHAVIOR_COPY: 'behavior_copy',
    TRANSITION_BEHAVIOR_PUBLISHING: 'behavior_clone',
    TRANSITION_BEHAVIOR_CHECKOUT: 'behavior_checkout',
    TRANSITION_BEHAVIOR_CHECKIN: 'behavior_checkin',
    TRANSITION_BEHAVIOR_FREEZE: 'behavior_freeze',
    TRANSITION_BEHAVIOR_MERGE: 'behavior_merge',

    TRANSITION_BEHAVIOR_PUSH_DELEGATEES: 'behavior_push_delegatees',
    TRANSITION_BEHAVIOR_POP_DELEGATEES: 'behavior_pop_delegatees',
    TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY:
    'behavior_return_up_delegatees_hierarchy',
    TRANSITION_BEHAVIOR_WORKFLOW_UP : 'behavior_workflow_up',
    TRANSITION_BEHAVIOR_WORKFLOW_DOWN : 'behavior_workflow_down',
    TRANSITION_BEHAVIOR_WORKFLOW_LOCK : 'behavior_workflow_lock',
    TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK : 'behavior_workflow_unlock',
    TRANSITION_BEHAVIOR_WORKFLOW_RESET : 'behavior_workflow_reset',
    }

class CPSTransitionDefinition(DCWFTransitionDefinition):
    """CPS Transition Definition

    It extends the DC Workfow Transition Definition by adding transition flags.
    """

    meta_type = 'CPS Workflow Transition'

    #
    # It holds the flag values
    #

    transition_behavior = ()

    #
    # Transitions allowed at destination
    #

    clone_allowed_transitions = []
    checkout_allowed_initial_transitions = []
    checkin_allowed_transitions = []

    #
    # Stack workflow transition flags
    # Workflow variables holding the stack workflow on which the transition
    # will be executed
    #

    push_on_workflow_variable = []
    pop_on_workflow_variable = []
    returned_up_hierarchy_on_workflow_variable = []
    workflow_up_on_workflow_variable = []
    workflow_down_on_workflow_variable = []
    workflow_lock_on_workflow_variable = []
    workflow_unlock_on_workflow_variable = []
    workflow_reset_on_workflow_variable = []

    _properties_form = DTMLFile('zmi/workflow_transition_properties',
                                globals())

    def setProperties(self,
                      title,
                      new_state_id,
                      transition_behavior=None,
                      clone_allowed_transitions=None,
                      checkout_allowed_initial_transitions=None,
                      checkin_allowed_transitions=None,
                      push_on_workflow_variable = None,
                      pop_on_workflow_variable = None,
                      returned_up_hierarchy_on_workflow_variable = None,
                      workflow_up_on_workflow_variable = None,
                      workflow_down_on_workflow_variable = None,
                      workflow_lock_on_workflow_variable = None,
                      workflow_unlock_on_workflow_variable = None,
                      workflow_reset_on_workflow_variable = None,
                      REQUEST=None,
                      **kw):
        """Set the properties."""
        if transition_behavior is not None:
            self.transition_behavior = tuple(transition_behavior)
        if clone_allowed_transitions is not None:
            self.clone_allowed_transitions = clone_allowed_transitions

        if checkout_allowed_initial_transitions is not None:
            self.checkout_allowed_initial_transitions = \
                checkout_allowed_initial_transitions
        if checkin_allowed_transitions is not None:
            self.checkin_allowed_transitions = checkin_allowed_transitions

        # Stack workflow transition flags
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

        # Now call original method.
        if REQUEST is not None:
            kw.update(REQUEST.form)
        prkw = {}
        for n in ('trigger_type', 'script_name', 'after_script_name',
                  'actbox_name', 'actbox_url', 'actbox_category',
                  'props', 'description'):
            if kw.has_key(n):
                prkw[n] = kw[n]
        return DCWFTransitionDefinition.setProperties(self,
                                                      title, new_state_id,
                                                      REQUEST=REQUEST,
                                                      **prkw)

    def getAvailableTransitionIds(self):
        return self.getWorkflow().transitions.keys()

    def getStackWorkflowVariablesForBehavior(self, behavior):
        """Returns the variables on wich the transition behavior applies
        """
        _behavior_variables = {
            TRANSITION_BEHAVIOR_PUSH_DELEGATEES :
                self.push_on_workflow_variable,
            TRANSITION_BEHAVIOR_POP_DELEGATEES  :
                self.pop_on_workflow_variable,
            TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY :
                self.returned_up_hierarchy_on_workflow_variable,
            TRANSITION_BEHAVIOR_WORKFLOW_UP   :
                self.workflow_up_on_workflow_variable,
            TRANSITION_BEHAVIOR_WORKFLOW_DOWN :
                self.workflow_down_on_workflow_variable,
            TRANSITION_BEHAVIOR_WORKFLOW_LOCK :
                self.workflow_lock_on_workflow_variable,
            TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK :
                self.workflow_unlock_on_workflow_variable,
            TRANSITION_BEHAVIOR_WORKFLOW_RESET  :
                self.workflow_reset_on_workflow_variable,
            }
        return _behavior_variables.get(behavior, ())

    def _getStackWorkflowFlagsRange(self):
        """Returns the range for stack workflow flags
        """
        return range(40, 50)

    def getAvailableStackWorkflowTransitionFlags(self):
        """Returns the transition flags defined on this transition related to
        stack workflows
        """
        _interested_behaviors = ()
        behaviors = self.transition_behavior
        for behavior in behaviors:
            if behavior in self._getStackWorkflowFlagsRange():
                _interested_behaviors += (behavior,)
        return _interested_behaviors

class CPSTransitions(DCWFTransitions):
    """CPS Transitions

    Extends DC Workflow Transition.  Actually, the goal is to new meta_type and
    use the CPSTransitionDefinition
    """

    meta_type = 'CPS Workflow Transitions'

    all_meta_types = ({'name':CPSTransitionDefinition.meta_type,
                       'action':'addTransition',
                       },)

    def addTransition(self, id, REQUEST=None):
        """Add a new transition to the workflow."""
        tdef = CPSTransitionDefinition(id)
        self._setObject(id, tdef)
        if REQUEST is not None:
            return self.manage_main(REQUEST, 'Transition added.')

    _manage_transitions = DTMLFile('zmi/workflow_transitions', globals())
