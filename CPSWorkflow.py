# -*- coding: iso-8859-15 -*-
# (C) Copyright 2002-2004 Nuxeo SARL <http://nuxeo.com>
# Author: Florent Guillaume <fg@nuxeo.com>
# Contributor : Julien Anguenot <ja@nuxeo.com>
#               - Refactoring CPS Workflow
#               - Stack Workflow support (transition flags)
#               - Workflow Guard enhanced
#               - Unit tests
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
It adds, as well, a stack workflow support to be able to define dynamic
delegation / validation chains through dedicated transitions.
"""

from zLOG import LOG, ERROR, DEBUG
from cgi import escape
from types import StringType

from Acquisition import aq_parent, aq_inner
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo, getSecurityManager

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import ManagePortal
from Products.CMFCore.WorkflowCore import ObjectMoved, ObjectDeleted
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFCore.WorkflowTool import addWorkflowFactory

from Products.DCWorkflow.DCWorkflow import DCWorkflowDefinition

from Products.DCWorkflow.Transitions \
    import TransitionDefinition as DCWFTransitionDefinition
from Products.DCWorkflow.Transitions import Transitions as DCWFTransitions
from Products.DCWorkflow.Transitions import TRIGGER_AUTOMATIC
from Products.DCWorkflow.Transitions import TRIGGER_USER_ACTION
from Products.DCWorkflow.Transitions import TRIGGER_WORKFLOW_METHOD
from Products.CPSCore.CPSWorkflowExpression import CPSStateChangeInfo as \
     StateChangeInfo
from Products.CPSCore.CPSWorkflowExpression import createExprContext

from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.utils import _isinstance
from Products.CPSCore.ProxyBase import ProxyBase

#
# Backwards compatibility with CPS3 <= 3.2.x
# Importing transition flags from here before.
#

from Products.CPSCore.CPSWorkflowTransitions import *
from Products.CPSCore.CPSWorkflowStates import *

class CPSWorkflowDefinition(DCWorkflowDefinition):
    """A Workflow implementation with enhanced transitions.

    Features:
    - Extended transition description,
    - Knowledge of proxies.
    """

    meta_type = 'CPS Workflow'
    title = 'CPS Workflow Definition'
    state_var = 'review_state'

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
    def notifyCreated(self, ob):
        """Notified when a CMF object has been created.

        Does nothing for CPS as all is done by wftool.invokeFactory.
        """
        pass

    security.declarePrivate('updateDelegateesLocalRolesFor')
    def updateDelegateesLocalRolesFor(self, ob, **kw):
        """Update local roles for delegatees that are within workflow stacks
        """
        changed = 0

        current_wf_var_id = kw.get('current_wf_var_id', '')
        wftool = aq_parent(aq_inner(self))
        stackdefs = wftool.getStackDefinitionsFor(ob)
        mtool = getToolByName(self, 'portal_membership')

        #
        # Let's ask the stack definition for the list of local roles
        #

        for stackdef in stackdefs.keys():

            # Update only the variable on wich the transition just applied
            if not stackdef == current_wf_var_id:
                continue

            ds = wftool.getInfoFor(ob, stackdef, self.id)
            former_mapping = stackdefs[stackdef].getFormerLocalRolesMapping(ds)
            mapping = stackdefs[stackdef].listLocalRoles(ds)

            #
            # First remove associated local roles to the ones who are not
            # supposed to have any
            #

            for id in former_mapping.keys():
                if id not in mapping.keys():
                    changed = 1
                    old_local_roles = former_mapping[id]
                    for old_local_role in old_local_roles:
                        if not id.startswith('group:'):
                            mtool.deleteLocalRoles(ob,
                                                   member_ids=[id],
                                                   member_role=old_local_role,
                                                   recursive=1)
                    else:
                        group_id = id[len('group:'):]
                        mtool.deleteLocalGroupRoles(ob,
                                                    ids=[group_id],
                                                    role=old_local_role)
            #
            # Add local roles to member / groups within the mapping
            #

            for id in mapping.keys():
                changed = 1
                local_roles = mapping[id]
                for local_role in local_roles:
                    if not id.startswith('group:'):
                        try:
                            mtool.setLocalRoles(ob,
                                                member_ids=[id],
                                                member_role=local_role)
                        except KeyError:
                            pass
                    else:
                        try:
                            group_id = id[len('group:'):]
                            mtool.setLocalGroupRoles(ob,
                                                     ids=[group_id],
                                                     role=local_role)
                        except KeyError:
                            pass

            #
            # Removing local roles for member / group (s) that have been
            # updated
            #

            for k in former_mapping.keys():
                if k in mapping.keys():
                    for old_local_role in former_mapping[k]:
                        if old_local_role not in mapping[k]:
                            changed = 1
                            if not k.startswith('group:'):
                                mtool.deleteLocalRoles(
                                    ob,
                                    member_ids=[k],
                                    member_role=old_local_role,
                                    recursive=1)
                            else:
                                group_id = k[len('group:'):]
                                mtool.deleteLocalGroupRoles(
                                    ob,
                                    ids=[group_id],
                                    role=old_local_role)
        return changed

    def updateRoleMappingsFor(self, ob, **kw):
        """Change the object permissions according to the current state.

        Change the local roles of the people eventually within workflow
        stacks. (CPS)

        Returns True if some change on an object was done.
        """

        # Update permissions according to the current state
        changed = DCWorkflowDefinition.updateRoleMappingsFor(self, ob)

        # Update Local roles according the workflow stack definitions
        delegatees_changed = self.updateDelegateesLocalRolesFor(ob, **kw)

        return (changed and delegatees_changed)

    def _checkStackGuards(self, t, ob):
        """Check the stack workflow transition guards on the transition for ob

        If one of them allowed the user to manage the stack it means the user
        is allowed to follow the transition
        """

        wftool = aq_parent(aq_inner(self))
        _interested_behaviors = t.getAvailableStackWorkflowTransitionFlags()

        # Check if stack workflow flags are defined on the transition
        if not _interested_behaviors:
            return 0

        #
        # Now check each interesting behaviors on this transition We will check
        # if the current authenticated user can manage one of the stack related
        # to the behavior
        #

        for behavior in _interested_behaviors:
            var_ids = t.getStackWorkflowVariablesForBehavior(behavior)
            for var_id in var_ids:
                if wftool.canManageStack(ob, var_id):
                    return 1

        return 0

    def _checkTransitionGuard(self, t, ob):
        """Check the transition guard

        DC workflow + stack def checks
        """
        guard = t.guard
        return (guard is None or
                guard.check(getSecurityManager(), self, ob) or
                self._checkStackGuards(t, ob))

    def _executeTransition(self, ob, tdef=None, kwargs=None):
        """Put the object in a new state, following transition tdef.

        Can be called at creation, when there is no current workflow
        state.
        """

        sci = None
        econtext = None
        moved_exc = None
        utool = getToolByName(self, 'portal_url') # CPS
        wftool = aq_parent(aq_inner(self))

        #
        # Ask the tool about stack definition instances. They will be
        # responsible for taking care about the actions to take
        # XXX change the name of this method
        #
        delegatees = wftool.getDelegateesDataStructures(ob)

        # Figure out the old and new states.
        old_sdef = self._getWorkflowStateOf(ob)
        ### CPS: Allow initial transitions to have no old state.
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


        ### CPS: Behavior sanity checks.
        #
        behavior = tdef.transition_behavior
        LOG('CPSWorkflow', DEBUG, 'Behavior in wf %s, trans %s: %s'
            % (self.getId(), tdef.getId(), behavior))
        kwargs = kwargs.copy() # Because we'll modify it.

        if TRANSITION_BEHAVIOR_MOVE in behavior:
            raise NotImplementedError
            ## Check allowed from source container.
            #src_container = aq_parent(aq_inner(ob))
            #ok, why = wftool.isBehaviorAllowedFor(src_container,
            #                                     TRANSITION_ALLOWSUB_MOVE,
            #                                     get_details=1)
            #if not ok:
            #    raise WorkflowException("src_container=%s does not allow "
            #                            "subobject move (%s)" %
            #                            (src_container.getId(), why))
            ## Now check dest container.
            #dest_container = kwargs.get('dest_container')
            #if dest_container is None:
            #    raise WorkflowException('Missing dest_container for move '
            #                            'transition=%s' % tdef.getId())
            #dest_container = self._objectMaybeFromRpath(dest_container)
            #ok, why = wftool.isBehaviorAllowedFor(dest_container, #XXXincorrect
            #                                     TRANSITION_INITIAL_MOVE,
            #                                  transition=self.dest_transition,
            #                                     get_details=1)
            #if not ok:
            #    raise WorkflowException("dst_container=%s does not allow "
            #                            "object initial move (%s)" %
            #                            (dst_container.getId(), why))
            #XXX now do move (recreate into dest container)
            #XXX raise ObjectDeleted ??? ObjectMoved ???
        if TRANSITION_BEHAVIOR_COPY in behavior:
            raise NotImplementedError
            #XXX
        if TRANSITION_BEHAVIOR_PUBLISHING in behavior:
            dest_container = kwargs.get('dest_container')
            if dest_container is None:
                raise WorkflowException("Missing dest_container for publishing"
                                        " transition=%s for ob=%s" %
                                        (tdef.getId(), ob))
            dest_container = self._objectMaybeFromRpath(dest_container)
            # Put it back so that it's useable from variables.
            kwargs['dest_container'] = utool.getRelativeUrl(dest_container)
            initial_transition = kwargs.get('initial_transition')
            if initial_transition is None:
                raise WorkflowException("Missing initial_transition for "
                                        "publishing transition=%s" %
                                        tdef.getId())
            if initial_transition not in tdef.clone_allowed_transitions:
                raise WorkflowException("Incorrect initial_transition %s, "
                                        "allowed=%s"
                                        % (initial_transition,
                                           tdef.clone_allowed_transitions))
        if TRANSITION_BEHAVIOR_CHECKOUT in behavior:
            dest_container = kwargs.get('dest_container')
            if dest_container is None:
                raise WorkflowException("Missing dest_container for checkout"
                                        " transition=%s" % tdef.getId())
            dest_container = self._objectMaybeFromRpath(dest_container)
            kwargs['dest_container'] = utool.getRelativeUrl(dest_container)
            initial_transition = kwargs.get('initial_transition')
            if initial_transition is None:
                raise WorkflowException("Missing initial_transition for "
                                        "checkout transition=%s" %
                                        tdef.getId())
            if initial_transition not in \
                    tdef.checkout_allowed_initial_transitions:
                raise WorkflowException("Incorrect initial_transition %s, "
                                        "allowed=%s"
                                        % (initial_transition,
                                    tdef.checkout_allowed_initial_transitions))
            language_map = kwargs.get('language_map')
        if TRANSITION_BEHAVIOR_CHECKIN in behavior:
            dest_objects = kwargs.get('dest_objects')
            if dest_objects is None:
                raise WorkflowException("Missing dest_objects for checkin"
                                        " transition=%s" % tdef.getId())
            dest_objects = [self._objectMaybeFromRpath(d)
                            for d in dest_objects]
            kwargs['dest_objects'] = [utool.getRelativeUrl(d)
                                      for d in dest_objects]
            checkin_transition = kwargs.get('checkin_transition')
            if checkin_transition is None:
                raise WorkflowException("Missing checkin_transition for "
                                        "checkin transition=%s" % tdef.getId())
            if checkin_transition not in tdef.checkin_allowed_transitions:
                raise WorkflowException("Incorrect checkin_transition %s, "
                                        "allowed=%s"
                                        % (checkin_transition,
                                           tdef.checkin_allowed_transitions))
            for dest_object in dest_objects:
                # Check that they have the same docid.
                if ob.getDocid() != dest_object.getDocid():
                    raise WorkflowException("Cannot checkin into different "
                                            "docid")
                # Check that the default language is still the same than
                # when we did checkout. # XXX We want to be more flexible.
                lang = ob.getDefaultLanguage()
                if (ob._getFromLanguageRevisions().get(lang, 1) !=
                    dest_object._getLanguageRevisions().get(lang, 2)):
                    raise WorkflowException("Cannot checkin into changed "
                                            "document %s" %
                                       '/'.join(dest_object.getPhysicalPath()))
        if TRANSITION_BEHAVIOR_DELETE in behavior:
            pass
            ## XXX Check that container allows delete.
            #container = aq_parent(aq_inner(ob))
            #ok, why = wftool.isBehaviorAllowedFor(container,
            #                                     TRANSITION_ALLOWSUB_DELETE,
            #                                     get_details=1)
            #if not ok:
            #    raise WorkflowException("Container=%s does not allow "
            #                            "subobject deletion (%s)" %
            #                            (container.getId(), why))
        #
        ###

        # Execute the "before" script.
        if tdef is not None and tdef.script_name:
            script = self.scripts[tdef.script_name]
            # Pass lots of info to the script in a single parameter.
            sci = StateChangeInfo(
                ob, self, former_status, tdef, old_sdef, new_sdef, delegatees, kwargs, )
            try:
                script(sci)  # May throw an exception.
            except ObjectMoved, moved_exc:
                ob = moved_exc.getNewObject()
                # Re-raise after transition

        ### CPS: Behavior.
        #

        delete_ob = None

        if TRANSITION_BEHAVIOR_MOVE in behavior:
            raise NotImplementedError
            #XXX now do move (recreate into dest container)
            #XXX raise ObjectDeleted ??? ObjectMoved ???

        if TRANSITION_BEHAVIOR_COPY in behavior:
            raise NotImplementedError
            #XXX

        if TRANSITION_BEHAVIOR_PUBLISHING in behavior:
            wftool.cloneObject(ob, dest_container, initial_transition, kwargs)

        if TRANSITION_BEHAVIOR_CHECKOUT in behavior:
            wftool.checkoutObject(ob, dest_container, initial_transition,
                                  language_map, kwargs)

        if TRANSITION_BEHAVIOR_CHECKIN in behavior:
            for dest_object in dest_objects:
                wftool.checkinObject(ob, dest_object, checkin_transition)
            # Now delete the original object.
            delete_ob = ob

        if TRANSITION_BEHAVIOR_FREEZE in behavior:
            # Freeze the object.
            if _isinstance(ob, ProxyBase):
                # XXX use an event?

                ob.freezeProxy()
                ob.proxyChanged()

        if TRANSITION_BEHAVIOR_DELETE in behavior:
            delete_ob = ob

        if TRANSITION_BEHAVIOR_MERGE in behavior:
            container = aq_parent(aq_inner(ob))
            dest_ob = wftool.mergeObject(ob, container,
                                         self.state_var, new_state)
            if dest_ob is not None:
                delete_ob = ob
                # Provide info to the UI to get a correct redirect.
                res = ('ObjectMoved', utool.getRelativeUrl(dest_ob))
                moved_exc = ObjectMoved(dest_ob, res)
                ob = dest_ob

        #################################################
        #              Stack workflows cases
        ##################################################

        if TRANSITION_BEHAVIOR_PUSH_DELEGATEES in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_PUSH_DELEGATEES",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            push_allowed_on_variables = new_sdef.push_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_PUSH_DELEGATEES not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_PUSH_DELEGATEES,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.push_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_PUSH_DELEGATEES,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in push_allowed_on_variables:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_PUSH_DELEGATEES,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    ds = delegatees.get(wf_var)
                    delegatees[wf_var] = stackdef.push(ds, **kwargs)

        if TRANSITION_BEHAVIOR_POP_DELEGATEES in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_POP_DELEGATEES",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #


            sdef_behaviors = new_sdef.state_behaviors
            pop_allowed_on_variables = new_sdef.pop_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_POP_DELEGATEES not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_POP_DELEGATEES,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.pop_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_POP_DELEGATEES,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in pop_allowed_on_variables:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_POP_DELEGATEES,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    ds = delegatees.get(wf_var)
                    delegatees[wf_var] = stackdef.pop(ds, **kwargs)

        if TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            return_vars = new_sdef.returned_up_hierarchy_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_RETURNED_UP_HIERARCHY not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_RETURNED_UP_HIERARCHY,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_down_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_RETURN_UP_DELEGATEES_HIERARCHY,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in return_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_RETURNED_UP_HIERARCHY,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    ds = delegatees.get(wf_var)
                    delegatees[wf_var] = stackdef.returnedUpDirection(ds, **kwargs)

        if TRANSITION_BEHAVIOR_WORKFLOW_UP in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_WORKFLOW_UP",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            up_vars = new_sdef.workflow_up_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_WORKFLOW_UP not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_WORKFLOW_UP,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_up_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_WORKFLOW_UP,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in up_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_WORKFLOW_UP,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    ds = delegatees.get(wf_var)
                    delegatees[wf_var] = stackdef.doIncLevel(ds)

        if TRANSITION_BEHAVIOR_WORKFLOW_DOWN in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_WORKFLOW_DOWN",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            down_vars = new_sdef.workflow_down_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_WORKFLOW_DOWN not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_WORKFLOW_DOWN,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_down_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_WORKFLOW_DOWN,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in down_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_WORKFLOW_DOWN,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    ds = delegatees.get(wf_var)
                    delegatees[wf_var] = stackdef.doDecLevel(ds)

        if TRANSITION_BEHAVIOR_WORKFLOW_LOCK in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_WORKFLOW_LOCK",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            lock_vars = new_sdef.workflow_lock_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_WORKFLOW_LOCK not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_WORKFLOW_LOCK,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_down_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_WORKFLOW_LOCK,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in lock_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_WORKFLOW_LOCK,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    stackdef.doLockStack()

        if TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            unlock_vars = new_sdef.workflow_unlock_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_WORKFLOW_UNLOCK not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_down_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_WORKFLOW_UNLOCK,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in unlock_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_WORKFLOW_UNLOCK,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    stackdef.doUnLockStack()

        if TRANSITION_BEHAVIOR_WORKFLOW_RESET in behavior:

            LOG("::CPSWorkflow._executeTansition() :: "
                "FLAG : TRANSITION_BEHAVIOR_WORKFLOW_RESET",
                DEBUG,
                str(kwargs))

            #
            # Get the stack definitions from the transition definition
            # The workflow variable id is the stackdef id.
            #

            sdef_behaviors = new_sdef.state_behaviors
            reset_vars = new_sdef.workflow_reset_on_workflow_variable

            #
            # First check if the state allows the behavior
            # Raise an exception if not allowed
            #

            if STATE_BEHAVIOR_WORKFLOW_RESET not in sdef_behaviors:
                raise WorkflowException(
                    "State behavior not allowed for '%s' on '%s'" %(
                    STATE_BEHAVIOR_WORKFLOW_RESET,
                    new_sdef.getId(),
                    ))

            wf_vars = tdef.workflow_reset_on_workflow_variable

            #
            # Raise an exception if not variables are associated to the
            # transition flag. Mostly for debuging right now. It's anyway a
            # problem of configuration
            #

            if not wf_vars:
                raise WorkflowException(
                    "Transition %s needs associated variables to execute on" %(
                    TRANSITION_BEHAVIOR_WORKFLOW_RESET,
                    ))

            for wf_var in wf_vars:

                #
                # Filter on the working workflow variable It's necessarly since
                # the transition can be allowed on several wf variable id
                #

                current_wf_var_id = kwargs.get('current_wf_var_id', '')
                if current_wf_var_id != wf_var:
                    continue

                #
                # Check here if the behavior is allowed by the state for this
                # given worfklow variable id
                #

                if wf_var not in reset_vars:
                    raise WorkflowException(
                        "State %s dosen't allow '%s' on var '%s'" %(
                        new_sdef.getId(),
                        STATE_BEHAVIOR_WORKFLOW_RESET,
                        wf_var,
                        ))

                stackdef = new_sdef.getDelegateesVarInfoFor(wf_var)
                if stackdef is not None:
                    stack = stackdef.resetStack()
                    delegatees[wf_var] = stackdef.resetStack(ds, **kwargs)

        #######################################################################
        #######################################################################

        #
        # Update variables.
        #

        state_values = new_sdef.var_values
        if state_values is None:
            state_values = {}
        tdef_exprs = None
        if tdef is not None:
            tdef_exprs = tdef.var_exprs
        if tdef_exprs is None:
            tdef_exprs = {}
        status = {}
        for id, vdef in self.variables.items():
            if not vdef.for_status:
                continue
            expr = None
            if state_values.has_key(id):
                value = state_values[id]
            elif tdef_exprs.has_key(id):
                expr = tdef_exprs[id]
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
                            old_sdef, new_sdef, delegatees, kwargs)
                    econtext = createExprContext(sci)
                value = expr(econtext)

            status[id] = value

        # Update state.
        status[self.state_var] = new_state
        tool = aq_parent(aq_inner(self))
        tool.setStatusOf(self.id, ob, status)

        ### CPS: Delete. Done after setting status, to keep history.
        #
        if delete_ob is not None:
            container = aq_parent(aq_inner(delete_ob))
            container._delObject(delete_ob.getId())
            if moved_exc is not None:
                raise moved_exc
            else:
                raise ObjectDeleted
        #
        ###

        # Update role to permission assignments.
        kw = {}
        kw['current_wf_var_id'] = kwargs.get('current_wf_var_id', '')
        self.updateRoleMappingsFor(ob, **kw)

        # Execute the "after" script.
        if tdef is not None and tdef.after_script_name:
            script = self.scripts[tdef.after_script_name]
            # Pass lots of info to the script in a single parameter.
            sci = StateChangeInfo(
                ob, self, status, tdef, old_sdef, new_sdef, delegatees, kwargs)
            script(sci)  # May throw an exception.

        ### CPS: Event notification. This has to be done after all the
        # potential transition scripts.
        #
        evtool = getEventService(self)
        # XXX pass a whole sci ?
        evtool.notify('workflow_%s' % tdef.getId(), ob, {'kwargs': kwargs})
        #
        ###

        # Return the new state object.
        if moved_exc is not None:
            # Propagate the notification that the object has moved.
            raise moved_exc
        else:
            return new_sdef


    #
    # API
    #

    security.declarePrivate('insertIntoWorkflow')
    def insertIntoWorkflow(self, ob, initial_transition, initial_behavior,
                           kwargs):
        """Insert an object into the workflow.

        The guard on the initial transition is evaluated in the
        context of the container of the object.

        (Called by WorkflowTool when inserting an object into the workflow
        after a create, copy, publishing, etc.)
        """
        tdef = self.transitions.get(initial_transition, None)
        if tdef is None:
            raise WorkflowException("No initial transition '%s'" %
                                    initial_transition)
        # Check it's really an initial transition.
        if initial_behavior not in tdef.transition_behavior:
            raise WorkflowException("workflow=%s transition=%s"
                                    " not a behavior=%s" %
                                    (self.getId(), initial_transition,
                                     initial_behavior))
        container = aq_parent(aq_inner(ob))
        if not self._checkTransitionGuard(tdef, container):
            raise WorkflowException("Unauthorized transition %s"
                                    % initial_transition)
        self._changeStateOf(ob, tdef, kwargs)


    security.declarePrivate('isBehaviorAllowedFor')
    def isBehaviorAllowedFor(self, ob, behavior, transition=None,
                             get_details=0):
        """Is the behavior allowed?

        Tests that the specified behavior is allowed in a transition.

        If transition is present, only check a transition with this name.
        """
        LOG('WF', DEBUG, 'isBehaviorAllowedFor ob=%s wf=%s beh=%s'
            % (ob.getId(), self.getId(), behavior))
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            if get_details:
                return 0, 'no state'
            else:
                return 0
        res = []
        for tid in sdef.transitions:
            if transition is not None and transition != tid:
                continue
            LOG('WF', DEBUG, ' Test transition %s' % tid)
            tdef = self.transitions.get(tid, None)
            if tdef is None:
                continue
            if behavior not in tdef.transition_behavior:
                LOG('WF', DEBUG, '  Not a %s' % (behavior,))
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
            return 0, ('state=%s (transition=%s) has no behavior=%s'
                       % (sdef.getId(), transition, behavior))
        else:
            return 0

    security.declarePrivate('getAllowedPublishingTransitions')
    def getAllowedPublishingTransitions(self, ob):
        """Get the list of allowed initial transitions for publishing."""
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            return []
        d = {}
        for tid in sdef.transitions:
            tdef = self.transitions.get(tid, None)
            if tdef is None:
                continue
            if TRANSITION_BEHAVIOR_PUBLISHING not in tdef.transition_behavior:
                continue
            if not self._checkTransitionGuard(tdef, ob):
                continue
            for t in tdef.clone_allowed_transitions:
                d[t] = None
        return d.keys()

    security.declarePrivate('getInitialTransitions')
    def getInitialTransitions(self, context, behavior):
        """Get the possible initial transitions in a context according to
        this workflow.

        context: the context in which the guard is evaluated.

        behavior: the type of initial transition to check for.

        Returns a sequence of transition names.
        """
        LOG('WF', DEBUG, "getInitialTransitions behavior=%s " % behavior)
        transitions = []
        for tdef in self.transitions.values():
            LOG('WF', DEBUG, ' Test transition %s' % tdef.getId())
            if behavior not in tdef.transition_behavior:
                LOG('WF', DEBUG, '  Not a %s' % behavior)
                continue
            if not self._checkTransitionGuard(tdef, context):
                LOG('WF', DEBUG, '  Guard failed')
                continue
            LOG('WF', DEBUG, '  Ok')
            transitions.append(tdef.getId())
        LOG('WF', DEBUG, ' Returning transitions=%s' % (transitions,))
        return transitions

    security.declarePrivate('getManagedPermissions')
    def getManagedPermissions(self):
        """Get the permissions managed by this workflow."""
        return self.permissions

    def _objectMaybeFromRpath(self, ob):
        if isinstance(ob, StringType):
            rpath = ob
            if not rpath or rpath.find('..') >= 0 or rpath.startswith('/'):
                raise WorkflowException("Unauthorized rpath %s" % rpath)
            portal = getToolByName(self, 'portal_url').getPortalObject()
            ob = portal.unrestrictedTraverse(rpath) # XXX unrestricted ?
        return ob

    # debug
    security.declarePrivate('listObjectActions')
    def listObjectActions(self, info):
        '''
        Allows this workflow to
        include actions to be displayed in the actions box.
        Called only when this workflow is applicable to
        info.content.
        Returns the actions to be displayed to the user.
        '''
        LOG('listObjectActions', DEBUG, 'Called for wf %s' % self.getId())
        ob = info.content
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            return None
        res = []
        for tid in sdef.transitions:
            LOG('listObjectActions', DEBUG, ' Checking %s' % tid)
            tdef = self.transitions.get(tid, None)
            if tdef is not None and tdef.trigger_type == TRIGGER_USER_ACTION:
                if tdef.actbox_name:
                    if self._checkTransitionGuard(tdef, ob):
                        res.append((tid, {
                            'id': tid,
                            'name': tdef.actbox_name % info,
                            'url': tdef.actbox_url % info,
                            'permissions': (),  # Predetermined.
                            'category': tdef.actbox_category}))
                        LOG('listObjectActions', DEBUG, '  Guard ok')
                    else:
                        LOG('listObjectActions', DEBUG, '  Guard failed')
                else:
                    LOG('listObjectActions', DEBUG, '  No user-visible action')
        res.sort()
        return map((lambda (id, val): val), res)

    #
    # XML Serialization
    #

    def _varExprsToXML(self, var_exprs, indent=''):
        nindent = indent + '  '
        if var_exprs is None:
            return indent + '<variables></variables>'
        contents = 'XXXTODO'
        return indent + _renderXMLTag('variables', contents=contents)

    def _permissionsToXML(self, permissions, indent=''):
        nindent = indent + '  '
        res = ['']
        for permission in permissions:
            res.append(nindent + _renderXMLTag('permission',
                                               contents=permission))
        res.append(indent)
        contents = '\n'.join(res)
        return indent + _renderXMLTag('permissions', contents=contents)

    def _rolesToXML(self, roles, indent=''):
        nindent = indent+'  '
        res = ['']
        for role in roles:
            res.append(nindent + _renderXMLTag('role', contents=role))
        res.append(indent)
        contents = '\n'.join(res)
        return indent + _renderXMLTag('roles', contents=contents)

    def _guardToXML(self, guard, indent=''):
        if guard is None:
            return indent+'<guard></guard>'
        nindent = indent+'  '
        res = ['']
        res.append(self._permissionsToXML(guard.permissions, indent=nindent))
        res.append(self._rolesToXML(guard.roles, indent=nindent))
        res.append(indent)
        contents = '\n'.join(res)
        return indent + _renderXMLTag('guard', contents=contents)

    def _behaviorsToXML(self, tdef, indent=''):
        nindent = indent+'  '
        res = ['']
        for behavior in tdef.transition_behavior:
            type = transition_behavior_export_dict.get(behavior, behavior)
            kwargs = {'type': type}
            if behavior == TRANSITION_BEHAVIOR_PUBLISHING:
                kwargs['transitions'] = ' '.join(
                    tdef.clone_allowed_transitions)
            elif behavior == TRANSITION_BEHAVIOR_CHECKOUT:
                kwargs['transitions'] = ' '.join(
                    tdef.checkout_allowed_initial_transitions)
            elif behavior == TRANSITION_BEHAVIOR_CHECKIN:
                kwargs['transitions'] = ' '.join(
                    tdef.checkin_allowed_transitions)
            res.append(nindent + _renderXMLTag('behavior', **kwargs))
        res.append(indent)
        behaviors = '\n'.join(res)
        return indent + _renderXMLTag('behaviors', contents=behaviors)

    def _transitionToXML(self, tid, indent=''):
        nindent = indent+'  '
        LOG('_transitionToXML', DEBUG, 'tid=%s' % `tid`)
        tdef = self.transitions.get(tid)
        trigger = trigger_export_dict.get(tdef.trigger_type,
                                          tdef.trigger_type)
        behaviors = self._behaviorsToXML(tdef, indent=nindent)
        guard = self._guardToXML(tdef.guard, indent=nindent)
        var_exprs = self._varExprsToXML(tdef.var_exprs, indent=nindent)
        contents = '\n'+behaviors+'\n'+guard+'\n'+var_exprs+'\n'+indent
        return indent + _renderXMLTag(
            'transition',
            id=tid,
            title=tdef.title,
            description=tdef.description,
            destination=tdef.new_state_id,
            trigger=trigger,
            actionName=tdef.actbox_name,
            actionUrl=tdef.actbox_url,
            actionCategory=tdef.actbox_category,
            beforeScript=tdef.script_name,
            afterScript=tdef.after_script_name,
            contents=contents)

    def _transitionsToXML(self, indent=''):
        nindent = indent+'  '
        res = ['']
        for tid in self.transitions.keys():
            res.append(self._transitionToXML(tid, indent=nindent))
        res.append(indent)
        contents = '\n'.join(res)
        return indent + _renderXMLTag('transitions', contents=contents)

    def toXML(self, indent=''):
        """Serialize the workflow to XML.

        Returns an XML string, without header.
        """
        nindent = indent + '  '
        contents = '\n' + self._transitionsToXML(indent=nindent) + '\n' + indent
        return _renderXMLTag('workflow', id=self.getId(),
                             title=self.title, contents=contents)

    #
    # ZMI
    #

    manage_options = DCWorkflowDefinition.manage_options + (
        {'label': 'Export', 'action': 'manage_exportWorkflow'},
        )

    security.declareProtected(ManagePortal, 'manage_exportWorkflow')
    manage_exportWorkflow = DTMLFile('zmi/workflow_export', globals())


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')


def _renderXMLTag(tagname, **kw):
    """Render an XML tag."""
    if kw.get('css_class'):
        kw['class'] = kw['css_class']
        del kw['css_class']
    if kw.has_key('contents'):
        contents = kw['contents']
        del kw['contents']
    else:
        contents = None
    attrs = []
    for key, value in kw.items():
        if value is None:
            value = key
        if value != '':
            attrs.append('%s="%s"' % (key, escape(str(value))))
    if attrs:
        res = '<%s %s>' % (tagname, ' '.join(attrs))
    else:
        res = '<%s>' % tagname
    if contents is not None:
        res += contents
    res += '</%s>' % tagname
    return res
