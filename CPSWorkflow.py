# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Workflow extending DCWorklfow with enhanced transitions.
"""

from zLOG import LOG, ERROR, DEBUG
from types import TupleType, IntType
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

from Products.DCWorkflow.DCWorkflow import TRIGGER_USER_ACTION
TRIGGER_CREATION = 10

TRANSITION_BEHAVIOR_NORMAL = 0
TRANSITION_BEHAVIOR_SUBCREATE = 1
TRANSITION_BEHAVIOR_CLONE = 2
TRANSITION_BEHAVIOR_FREEZE = 3
TRANSITION_BEHAVIOR_SUBDELETE = 4
TRANSITION_BEHAVIOR_SUBCOPY = 5


class CPSStateDefinition(DCWFStateDefinition):
    meta_type = 'CPS Workflow State'


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


class CPSTransitionDefinition(DCWFTransitionDefinition):
    meta_type = 'CPS Workflow Transition'

    transition_behavior = ()
    clone_allowed_transitions = []
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
            self.transition_behavior = tuple(transition_behavior)
        if clone_allowed_transitions is not None:
            self.clone_allowed_transitions = clone_allowed_transitions
        if checkout_original_transition_id is not None:
            self.checkout_original_transition_id = checkout_original_transition_id
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


class CPSTransitions(DCWFTransitions):
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


class CPSWorkflowDefinition(DCWorkflowDefinition):
    """A Workflow implementation with enhanced transitions.

    Features:
    - Extended transition description,
    - Knowledge of proxies.
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
        The guard on the creation transition is evaluated in the
        context of the container.
        """
        if creation_transition is None:
            LOG('notifyCreated', DEBUG, 'Workflow %s called without a '
                'creation_transition' % self.getId())
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

    security.declarePrivate('updateRoleMappingsFor')
    def updateRoleMappingsFor(self, ob):
        """Change the object permissions according to the current state.

        Returns True if some change on an object was done.
        """
        return DCWorkflowDefinition.updateRoleMappingsFor(self, ob)
        # XXX also send event

    def _executeTransition(self, ob, tdef=None, kwargs=None):
        """Put the object in a new state, following transition tdef.

        Can be called at creation, when there is no current workflow
        state.
        """
        sci = None
        econtext = None
        moved_exc = None

        # Figure out the old and new states.
        old_sdef = self._getWorkflowStateOf(ob)
        ### CPS: Allow creation transitions to have no old state.
        #
        if old_sdef is not None:
            old_state = old_sdef.getId()
        else:
            old_state = None
        #
        ###
        if tdef is None:
            # CPS: tdef is never None for CPSWorkflow
            raise WorkflowException('No transition!')
            #new_state = self.initial_state
            #former_status = {}
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

        ### CPS: Behavior.
        #
        LOG('CPSWorkflow', DEBUG, 'Behavior in wf %s, trans %s: %s'
            % (self.getId(), tdef.getId(), tdef.transition_behavior))
        # XXX forward-compatibility
        behavior = tdef.transition_behavior
        if not isinstance(behavior, TupleType):
            behavior = (behavior,)
        if TRANSITION_BEHAVIOR_CLONE in behavior:
            # Clone the object.
            clone_data = kwargs.get('clone_data')
            if clone_data is None:
                raise WorkflowException('Missing clone_data for clone '
                                        'transition %s' % tdef.getid())
            wftool = aq_parent(aq_inner(self))
            portal = aq_parent(aq_inner(wftool))
            for container_path, creation_transitions in clone_data.items():
                container = portal.restrictedTraverse(container_path)
                wftool.cloneObject(ob, container, creation_transitions)
        if TRANSITION_BEHAVIOR_FREEZE in behavior:
            # Freeze the object.
            # XXX use an event?
            ob.freezeProxy()
        #
        ###

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

    def _hasTransitionBehaviors(self, ob, behaviors, get_details=0):
        """Is some behaviors allowed ?

        Tests that all the specified behaviors are allowed in a single
        transition.
        """
        LOG('WF', DEBUG, '_hasTransitionBehavior ob=%s wf=%s beh=%s'
            % (ob.getId(), self.getId(), behaviors))
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            if get_details:
                return 0, 'no state'
            else:
                return 0
        if isinstance(behaviors, IntType):
            behaviors = [behaviors]
        res = []
        for tid in sdef.transitions:
            LOG('WF', DEBUG, ' Test transition %s' % tid)
            tdef = self.transitions.get(tid, None)
            if tdef is None:
                continue
            transition_behavior = tdef.transition_behavior
            # XXX forward-compatibility
            if not isinstance(transition_behavior, TupleType):
                transition_behavior = (transition_behavior,)
            ok = 1
            for behavior in behaviors:
                if behavior not in transition_behavior:
                    LOG('WF', DEBUG, '  Not a %s' % (behavior,))
                    ok = 0
                    break
            if not ok:
                continue
            if not self._checkTransitionGuard(tdef, ob):
                LOG('WF', DEBUG, '  Guard failed')
                continue
            LOG('WF', DEBUG, '  Ok')
            if get_details:
                return 1, ''
            else:
                return 1
        if get_details:
            return 0, 'state %s has no %s behavior' % (sdef.getId(), behavior)
        else:
            return 0

    security.declarePrivate('areBehaviorsAllowedIn')
    def areBehaviorsAllowedIn(self, ob, behaviors, get_details=0):
        """Are all these behaviors allowed ?"""
        return self._hasTransitionBehaviors(ob, behaviors,
                                            get_details=get_details)

    security.declarePrivate('getCreationTransitions')
    def getCreationTransitions(self, container):
        """Get the possible creation transitions according to this
        workflow.

        The container is the context in which the guard is evaluated.
        """
        LOG('WF', DEBUG, 'wf=%s get creationtransitions' % self.getId())
        res = []
        for tdef in self.transitions.values():
            LOG('WF', DEBUG, '  trans %s' % tdef.getId())
            if tdef.trigger_type != TRIGGER_CREATION:
                LOG('WF', DEBUG, '    no, not creation')
                continue
            if not self._checkTransitionGuard(tdef, container):
                LOG('WF', DEBUG, '    no, not guard')
                continue
            LOG('WF', DEBUG, '    ok')
            res.append(tdef.getId())
        res.sort()
        LOG('WF', DEBUG, '  returning %s' % `res`)
        return res

    security.declarePrivate('getCloneAllowedTransitions')
    def getCloneAllowedTransitions(self, ob):
        """Get the list of allowed initial transitions for clone."""
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            return []
        res = []
        for tid in sdef.transitions:
            tdef = self.transitions.get(tid, None)
            if tdef is None:
                continue
            # XXX forward-compatibility
            behavior = tdef.transition_behavior
            if not isinstance(behavior, TupleType):
                behavior = (behavior,)
            if TRANSITION_BEHAVIOR_CLONE not in behavior:
                continue
            if not self._checkTransitionGuard(tdef, ob):
                continue
            allowed = tdef.clone_allowed_transitions
            res.extend([t for t in allowed if t not in res])
        return res

    security.declarePrivate('getManagedPermissions')
    def getManagedPermissions(self):
        """Get the permissions managed by this workflow."""
        return self.permissions


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')
