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
from types import StringType
from Acquisition import aq_base, aq_parent, aq_inner
from Globals import InitializeClass, PersistentMapping, DTMLFile
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import ObjectMoved, ObjectDeleted
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFCore.WorkflowTool import addWorkflowFactory

from Products.DCWorkflow.DCWorkflow import DCWorkflowDefinition
from Products.DCWorkflow.States import StateDefinition as DCWFStateDefinition
from Products.DCWorkflow.States import States as DCWFStates
from Products.DCWorkflow.Transitions import TransitionDefinition as DCWFTransitionDefinition
from Products.DCWorkflow.Transitions import Transitions as DCWFTransitions
from Products.DCWorkflow.Transitions import TRIGGER_USER_ACTION
from Products.DCWorkflow.Expression import StateChangeInfo
from Products.DCWorkflow.Expression import createExprContext

from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.cpsutils import _isinstance
from Products.CPSCore.ProxyBase import ProxyBase

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
    checkout_allowed_initial_transitions = []
    checkin_allowed_transitions = []

    _properties_form = DTMLFile('zmi/workflow_transition_properties',
                                globals())

    def setProperties(self, title, new_state_id,
                      transition_behavior=None,
                      clone_allowed_transitions=None,
                      checkout_allowed_initial_transitions=None,
                      checkin_allowed_transitions=None,
                      REQUEST=None, **kw):
        """Set the properties."""
        if transition_behavior is not None:
            self.transition_behavior = tuple(transition_behavior)
        if clone_allowed_transitions is not None:
            self.clone_allowed_transitions = clone_allowed_transitions
        if checkout_allowed_initial_transitions is not None:
            self.checkout_allowed_initial_transitions = checkout_allowed_initial_transitions
        if checkin_allowed_transitions is not None:
            self.checkin_allowed_transitions = checkin_allowed_transitions
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
    def notifyCreated(self, ob):
        """Notified when a CMF object has been created.

        Does nothing for CPS as all is done by wftool.invokeFactory.
        """
        pass

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

        utool = getToolByName(self, 'portal_url') # CPS

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
        wftool = aq_parent(aq_inner(self))
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
                                        " transition=%s" % tdef.getId())
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
            if initial_transition not in tdef.checkout_allowed_initial_transitions:
                raise WorkflowException("Incorrect initial_transition %s, "
                                        "allowed=%s"
                                        % (initial_transition,
                                    tdef.checkout_allowed_initial_transitions))
            language_map = kwargs.get('language_map')
            if language_map is None:
                raise WorkflowException("Missing language_map for "
                                        "checkout transition=%s" %
                                        tdef.getId())

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

        ### CPS: Event notification.
        #
        evtool = getEventService(self)
        # XXX pass a whole sci ?
        infos = {'kw': kwargs}
        evtool.notify('workflow_%s' % tdef.getId(), ob, infos)
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

        ### CPS: Behavior.
        #

        do_delete = 0

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
            do_delete = 1

        if TRANSITION_BEHAVIOR_FREEZE in behavior:
            # Freeze the object.
            if _isinstance(ob, ProxyBase):
                # XXX use an event?
                ob.freezeProxy()
                ob.proxyChanged()

        if TRANSITION_BEHAVIOR_DELETE in behavior:
            do_delete = 1
        #
        ###

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

        ### CPS: Delete. Done after setting status, to keep history.
        #
        if do_delete:
            container = aq_parent(aq_inner(ob))
            container._delObject(ob.getId())
            raise ObjectDeleted
        #
        ###

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
                raise Unauthorized(rpath)
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


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')
