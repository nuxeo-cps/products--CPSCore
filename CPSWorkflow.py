# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
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
"""Workflow extending DCWorklfow with proxy support and creation states.
"""

from zLOG import LOG, ERROR, DEBUG
from Acquisition import aq_base, aq_parent, aq_inner
from Globals import InitializeClass, PersistentMapping, DTMLFile
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName

from Products.CMFCore.WorkflowCore import ObjectDeleted, ObjectMoved
from Products.CMFCore.WorkflowTool import addWorkflowFactory

from Products.DCWorkflow.DCWorkflow import DCWorkflowDefinition
from Products.DCWorkflow.States import StateDefinition as DCWFStateDefinition
from Products.DCWorkflow.States import States as DCWFStates
from Products.DCWorkflow.Transitions import TransitionDefinition as DCWFTransitionDefinition
from Products.DCWorkflow.Transitions import Transitions as DCWFTransitions


TRIGGER_CREATION = 50

TRANSITION_BEHAVIOR_NORMAL = 0


class CPSStateDefinition(DCWFStateDefinition):
    meta_type = 'CPS Workflow State'


class CPSStates(DCWFStates):
    meta_type = 'CPS Workflow States'

    def addState(self, id, REQUEST=None):
        """Add a new state to the workflow."""
        sdef = CPSStateDefinition(id)
        self._setObject(id, sdef)
        if REQUEST is not None:
            return self.manage_main(REQUEST, 'State added.')


class CPSTransitionDefinition(DCWFTransitionDefinition):
    meta_type = 'CPS Workflow Transition'

    transition_behavior = TRANSITION_BEHAVIOR_NORMAL
    clone_allowed_transitions = ''
    checkout_original_transition_id = ' '

    _properties_form = DTMLFile('zmi/workflow_transition_properties',
                                globals())

    def setProperties(self, title, new_state_id,
                      transition_behavior=None,
                      clone_allowed_transitions=None,
                      checkout_original_transition_id=None,
                      REQUEST=None, **kw):
        """Set the properties."""
        if transition_behavior is not None:
            self.transition_behavior = transition_behavior
        if clone_allowed_transitions is not None:
            self.clone_allowed_transitions = clone_allowed_transitions
        if checkout_original_transition_id is not None:
            self.checkout_original_transition_id = checkout_original_transition_id
        # Now call original method.
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


class CPSTransitions(DCWFTransitions):
    meta_type = 'CPS Workflow Transitions'

    def addTransition(self, id, REQUEST=None):
        """Add a new transition to the workflow."""
        tdef = CPSTransitionDefinition(id)
        self._setObject(id, tdef)
        if REQUEST is not None:
            return self.manage_main(REQUEST, 'Transition added.')


class CPSWorkflowDefinition(DCWorkflowDefinition):
    """A Workflow implementation with proxy support.

    Features:
    - Creation transitions (those from the uncreated_ state)
    - Extended transition description
    """

    meta_type = 'CPS Workflow'
    title = 'CPS Workflow Definition'

    security = ClassSecurityInfo()

    def __init__(self, id):
        self.id = id
        # CPS versions
        self._addObject(CPSStates('states'))
        self._addObject(CPSTransitions('transitions'))
        # Normal DCWorkflow versions
        from Products.DCWorkflow.Variables import Variables
        self._addObject(Variables('variables'))
        from Products.DCWorkflow.Worklists import Worklists
        self._addObject(Worklists('worklists'))
        from Products.DCWorkflow.Scripts import Scripts
        self._addObject(Scripts('scripts'))

    #
    # Overloads
    #

    security.declarePrivate('notifyCreated')
    def notifyCreated(self, ob, creation_transition=None):
        """Notified when a CMF object has been created.

        Only does workflow insertion if called with a
        creation_transition.
        """
        if creation_transition is None:
            return
        tdef = self.transitions.get(creation_transition, None)
        if tdef is None:
            raise WorkflowException("No creation transition '%s'" %
                                    creation_transition)
        if tdef.trigger_type != TRIGGER_CREATION:
            raise WorkflowException("Transition %s is not a creation "
                                    "transition" % creation_transition)
        container = aq_parent(aq_inner(ob))
        if not self._checkTransitionGuard(tdef, container):
            LOG('CPSWorkflowDefinition', DEBUG, "notifyCreated "
                "Unauthorized transition %s" % creation_transition)
            raise Unauthorized
        self._changeStateOf(ob, tdef)

    def _executeTransition(self, ob, tdef=None, kwargs=None):
        """Put the object in a new state, following transition tdef."""
        sci = None
        econtext = None
        moved_exc = None

        # Figure out the old and new states.
        old_sdef = self._getWorkflowStateOf(ob)
        ### CPS modification
        #
        if old_sdef is not None:
            old_state = old_sdef.getId()
        else:
            old_state = None
        #
        ###
        if tdef is None:
            new_state = self.initial_state
            former_status = {}
        else:
            new_state = tdef.new_state_id
            if not new_state:
                # Stay in same state.
                new_state = old_state
            former_status = self._getStatusOf(ob)
        new_sdef = self.states.get(new_state, None)
        if new_sdef is None:
            raise WorkflowException, (
                'Destination state undefined: ' + new_state)

        # Execute the "before" script.
        if tdef is not None and tdef.script_name:
            script = self.scripts[tdef.script_name]
            # Pass lots of info to the script in a single parameter.
            sci = StateChangeInfo(
                ob, self, former_status, tdef, old_sdef, new_sdef, kwargs)
            try:
                script(sci)  # May throw an exception.
            except ObjectMoved, moved_exc:
                ob = moved_exc.getNewObject()
                # Re-raise after transition

        # Update variables.
        state_values = new_sdef.var_values
        if state_values is None: state_values = {}
        tdef_exprs = None
        if tdef is not None: tdef_exprs = tdef.var_exprs
        if tdef_exprs is None: tdef_exprs = {}
        status = {}
        for id, vdef in self.variables.items():
            if not vdef.for_status:
                continue
            expr = None
            if state_values.has_key(id):
                value = state_values[id]
            elif tdef_exprs.has_key(id):
                expr = tdef_exprs[id]
            elif not vdef.update_always and former_status.has_key(id):
                # Preserve former value
                value = former_status[id]
            else:
                if vdef.default_expr is not None:
                    expr = vdef.default_expr
                else:
                    value = vdef.default_value
            if expr is not None:
                # Evaluate an expression.
                if econtext is None:
                    # Lazily create the expression context.
                    if sci is None:
                        sci = StateChangeInfo(
                            ob, self, former_status, tdef,
                            old_sdef, new_sdef, kwargs)
                    econtext = createExprContext(sci)
                value = expr(econtext)
            status[id] = value

        # Update state.
        status[self.state_var] = new_state
        tool = aq_parent(aq_inner(self))
        tool.setStatusOf(self.id, ob, status)

        # Update role to permission assignments.
        self.updateRoleMappingsFor(ob)

        # Execute the "after" script.
        if tdef is not None and tdef.after_script_name:
            script = self.scripts[tdef.after_script_name]
            # Pass lots of info to the script in a single parameter.
            sci = StateChangeInfo(
                ob, self, status, tdef, old_sdef, new_sdef, kwargs)
            script(sci)  # May throw an exception.

        # Return the new state object.
        if moved_exc is not None:
            # Propagate the notification that the object has moved.
            raise moved_exc
        else:
            return new_sdef


    #
    # API
    #

    security.declarePrivate('getCreationTransitions')
    def getCreationTransitions(self, container):
        """Get the possible creation transitions."""
        res = []
        for tdef in self.transitions.values():
            if tdef.trigger_type != TRIGGER_CREATION:
                continue
            if not self._checkTransitionGuard(tdef, container):
                continue
            res.append(tdef.getId())
        res.sort()
        return tuple(res)


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')
