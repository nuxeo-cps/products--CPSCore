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
"""Workflow Tool with CPS proxy knowledge and CPS placeful workflow support.
"""

from zLOG import LOG, ERROR, DEBUG
from types import StringType
from Acquisition import aq_base, aq_parent, aq_inner
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo, Unauthorized

from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.CMFCorePermissions import ManagePortal
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFCore.WorkflowTool import WorkflowTool

from Products.CPSCore.utils import _isinstance

from Products.CPSCore.ProxyBase import ProxyBase, ProxyFolderishDocument
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_CREATE
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_DELETE
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_MOVE
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_COPY
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_PUBLISHING
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOWSUB_CHECKOUT
from Products.CPSCore.CPSWorkflow import TRANSITION_INITIAL_CREATE
from Products.CPSCore.CPSWorkflow import TRANSITION_INITIAL_MOVE
from Products.CPSCore.CPSWorkflow import TRANSITION_INITIAL_COPY
from Products.CPSCore.CPSWorkflow import TRANSITION_INITIAL_PUBLISHING
from Products.CPSCore.CPSWorkflow import TRANSITION_INITIAL_CHECKOUT
from Products.CPSCore.CPSWorkflow import TRANSITION_ALLOW_CHECKIN
from Products.CPSCore.CPSWorkflow import TRANSITION_BEHAVIOR_PUBLISHING


CPSWorkflowConfig_id = '.cps_workflow_configuration'


class CPSWorkflowTool(WorkflowTool):
    """A Workflow Tool extending the CMFCore one with CPS features.

    - Initial transition knowledge for CPSWorkflow
    - Placefulness
    - Delegates storage of workflow history for proxies to repository tool
    """

    id = 'portal_workflow'
    meta_type = 'CPS Workflow Tool'
    title = 'CPS Workflow Tool'

    security = ClassSecurityInfo()

    # We don't need a default default chain
    _default_chain = ()

    #def __init__(self):
    #    pass

    #
    # Allow user code access to constants.
    #

    TRANSITION_INITIAL_CREATE =      TRANSITION_INITIAL_CREATE
    TRANSITION_INITIAL_PUBLISHING =  TRANSITION_INITIAL_PUBLISHING
    TRANSITION_BEHAVIOR_PUBLISHING = TRANSITION_BEHAVIOR_PUBLISHING

    #
    # API
    #
    security.declarePublic('isCreationAllowedIn')
    def isCreationAllowedIn(self, container, get_details=0):
        """Is the creation of a subobject allowed in the container ?"""
        return self.isBehaviorAllowedFor(container, 'create',
                                         get_details=get_details)

    security.declarePublic('isBehaviorAllowedFor')
    def isBehaviorAllowedFor(self, container, behavior, transition=None,
                             get_details=0):
        """Is some behavior allowed in the container?

        If transition is present, only check a transition with this name.
        """
        behavior = {
            'create': TRANSITION_ALLOWSUB_CREATE,
            'delete': TRANSITION_ALLOWSUB_DELETE,
            'cut':    TRANSITION_ALLOWSUB_MOVE,
            'copy':   TRANSITION_ALLOWSUB_COPY,
            'paste':  TRANSITION_ALLOWSUB_CREATE,
            }.get(behavior, behavior)
        for wf in self.getWorkflowsFor(container):
            # XXX deal with non-CPS workflows
            ok, why = wf.isBehaviorAllowedFor(container, behavior,
                                              transition, get_details=1)
            if not ok:
                LOG('isBehaviorAllowedFor', DEBUG, 'not ok for %s: %s' %
                    (behavior, why))
                if get_details:
                    return 0, '%s, %s' % (wf.getId(), why)
                else:
                    return 0
        if get_details:
            return 1, ''
        else:
            return 1

    security.declarePublic('getAllowedPublishingTransitions')
    def getAllowedPublishingTransitions(self, ob):
        """Get the list of allowed initial transitions for publishing."""
        d = {}
        for wf in self.getWorkflowsFor(ob):
            if not hasattr(aq_base(wf), 'getAllowedPublishingTransitions'):
                # Not a CPS workflow.
                continue
            for t in wf.getAllowedPublishingTransitions(ob):
                d[t] = None
        transitions = d.keys()
        transitions.sort()
        return transitions

    security.declarePublic('getInitialTransitions')
    def getInitialTransitions(self, container, type_name, behavior):
        """Get the initial transitions for a type in a container.

        container: can be an rpath.

        type_name: the portal type to check.

        behavior: the type of transition to check for.

        Returns a sequence of transition names.
        """
        container = self._container_maybe_rpath(container)
        LOG('CPSWFT', DEBUG,
            "getInitialTransitions container=%s type_name=%s behavior=%s "
            % ('/'.join(container.getPhysicalPath()), type_name, behavior))
        d = {}
        for wf_id in self.getChainFor(type_name, container=container):
            wf = self.getWorkflowById(wf_id)
            if wf is None:
                # Incorrect workflow name in chain.
                continue
            if not hasattr(aq_base(wf), 'getInitialTransitions'):
                # Not a CPS workflow.
                continue
            for t in wf.getInitialTransitions(container, behavior):
                d[t] = None
        transitions = d.keys()
        transitions.sort()
        LOG('CPSWFT', DEBUG, "  Transitions are %s" % `transitions`)
        return transitions

    def _container_maybe_rpath(self, container):
        if isinstance(container, StringType):
            rpath = container
            if not rpath or rpath.find('..') >= 0 or rpath.startswith('/'):
                raise ValueError(rpath)
            portal = aq_parent(aq_inner(self))
            container = portal.unrestrictedTraverse(rpath)
        return container

    security.declarePublic('getDefaultLanguage')
    def getDefaultLanguage(self):
        """Get the default language for a new object."""
        portal = aq_parent(aq_inner(self))
        if hasattr(portal, 'Localizer'):
            return portal.Localizer.get_default_language()
        else:
            return 'en'

    security.declarePublic('invokeFactoryFor')
    def invokeFactoryFor(self, container, type_name, id,
                         language=None, initial_transition=None,
                         *args, **kw):
        """Create an object in a container.

        The variable initial_transition is the initial transition to use
        (in all workflows). If None, use the first initial transition
        for 'create' found.

        The object created will be a proxy to a real object if the type
        type_name has an property of id 'cps_proxy_type' and of value
        'folder', 'document' or 'folderishdocument'.
        """
        container = self._container_maybe_rpath(container)
        LOG('invokeFactoryFor', DEBUG,
            "Called with container=%s type_name=%s id=%s "
            "language=%s initial_transition=%s" %
            (container.getId(), type_name, id, language, initial_transition))
        if language is None:
            language = self.getDefaultLanguage()
        if initial_transition is None:
            # If no initial transition is mentionned, find a default.
            crtrans = self.getInitialTransitions(container, type_name,
                                                 TRANSITION_INITIAL_CREATE)
            if len(crtrans) == 1:
                initial_transition = crtrans[0]
            else:
                raise WorkflowException(
                    "No initial_transition to create %s (type_name=%s) in %s"
                    % (id, type_name, container.getId()))
        ob = self._createObject(container, id,
                                initial_transition, TRANSITION_INITIAL_CREATE,
                                language=language, type_name=type_name,
                                kwargs=kw)
        return ob.getId()

    security.declarePublic('findNewId')
    def findNewId(self, container, id):
        """Find what will be the new id of an object created in a container."""
        container = self._container_maybe_rpath(container)
        base_container = aq_base(container)
        if hasattr(base_container, id):
            # Collision, find a free one.
            i = 0
            while 1:
                i += 1
                try_id = '%s_%d' % (id, i)
                if not hasattr(base_container, try_id):
                    id = try_id
                    break
        return id

    security.declarePrivate('cloneObject')
    def cloneObject(self, ob, container, initial_transition, kwargs):
        """Clone ob into container according to some initial transition.

        (Called by a CPS workflow during publishing transition.)
        """
        LOG('cloneObject', DEBUG, 'Called with ob=%s container=%s '
            'initial_transition=%s' % (ob.getId(), container.getId(),
                                       initial_transition))
        id = self.findNewId(container, ob.getId())
        new_ob = self._createObject(container, id,
                                    initial_transition,
                                    TRANSITION_INITIAL_PUBLISHING,
                                    old_ob=ob, kwargs=kwargs)
        return new_ob


    security.declarePrivate('checkoutObject')
    def checkoutObject(self, ob, container, initial_transition,
                       language_map, kwargs):
        """Checkout ob into container according to some initial transition.

        Checkout the languages according to the language map.

        (Called by CPS Workflow during checkout transition.)
        """
        LOG('checkoutObject', DEBUG, "Called with ob=%s container=%s "
            "initial_transition=%s language_map=%s" %
            (ob.getId(), container.getId(), initial_transition, language_map))
        id = self.findNewId(container, ob.getId())
        new_ob = self._createObject(container, id,
                                    initial_transition,
                                    TRANSITION_INITIAL_CHECKOUT,
                                    language_map=language_map,
                                    old_ob=ob, kwargs=kwargs)
        return new_ob

    def _createObject(self, container, id,
                      initial_transition, initial_behavior,
                      language=None, type_name=None, old_ob=None,
                      language_map=None,
                      kwargs={}):
        """Create an object in a container, according to initial behavior."""
        LOG('_createObject', DEBUG, 'Called with container=%s id=%s '
            'initial_transition=%s' % (container.getId(), id,
                                       initial_transition))
        pxtool = getToolByName(self, 'portal_proxies')

        # Check that the workflow of the container allows sub behavior.
        subbehavior = {
            TRANSITION_INITIAL_CREATE:     TRANSITION_ALLOWSUB_CREATE,
            TRANSITION_INITIAL_MOVE:       TRANSITION_ALLOWSUB_MOVE,
            TRANSITION_INITIAL_COPY:       TRANSITION_ALLOWSUB_COPY,
            TRANSITION_INITIAL_PUBLISHING: TRANSITION_ALLOWSUB_PUBLISHING,
            TRANSITION_INITIAL_CHECKOUT:   TRANSITION_ALLOWSUB_CHECKOUT,
            }.get(initial_behavior)
        if subbehavior is None:
            raise WorkflowException("Incorrect initial_behavior=%s" %
                                    initial_behavior)
        ok, why = self.isBehaviorAllowedFor(container, subbehavior,
                                            get_details=1)
        if not ok:
            if why:
                details = 'not allowed by workflow %s' % why
            else:
                details = 'no workflow'
            raise WorkflowException("Container %s does not allow "
                                    "subobject behavior %s (%s)" %
                                    (container.getId(),
                                     subbehavior, details))
        # Find type to create.
        if initial_behavior != TRANSITION_INITIAL_CREATE:
            type_name = old_ob.getPortalTypeName()
        # Find out if we must create a normal document or a proxy.
        # XXX determine what's the best way to parametrize this
        proxy_type = None
        ttool = getToolByName(self, 'portal_types')
        for ti in ttool.listTypeInfo():
            if ti.getId() != type_name:
                continue
            proxy_type = getattr(ti, 'cps_proxy_type', None)
            break

        if initial_behavior == TRANSITION_INITIAL_PUBLISHING:
            ob = container.copyContent(old_ob, id)
            ob.manage_afterCMFAdd(ob, container)
            self._insertWorkflowRecursive(ob, initial_transition,
                                          initial_behavior, kwargs)
        elif initial_behavior == TRANSITION_INITIAL_CREATE:
            if not proxy_type:
                # XXX constructContent doesn't exist everywhere !
                # XXX especially when creating at the root of the portal.
                ob = container.constructContent(type_name, id, **kwargs)
            else:
                # Create a proxy and a document in the repository.
                proxy = pxtool.createEmptyProxy(proxy_type, container,
                                                type_name, id)
                pxtool.createRevision(proxy, language, **kwargs)
                # Set the first language as default language.
                proxy.setDefaultLanguage(language)
                ob = proxy
            ob.manage_afterCMFAdd(ob, container)
            self._insertWorkflow(ob, initial_transition, initial_behavior,
                                 kwargs)
        elif initial_behavior == TRANSITION_INITIAL_CHECKOUT:
            if not _isinstance(old_ob, ProxyBase):
                raise WorkflowException("Can't checkout non-proxy object %s"
                                        % '/'.join(old_ob.getPhysicalPath()))
            old_proxy = old_ob
            from_language_revs = old_proxy.getLanguageRevisions()
            docid = old_proxy.getDocid()
            proxy = pxtool.createEmptyProxy(proxy_type, container,
                                            type_name, id, docid)
            pxtool.checkoutRevisions(old_proxy, proxy, language_map)
            proxy.setDefaultLanguage(old_proxy.getDefaultLanguage())
            proxy.setFromLanguageRevisions(from_language_revs)
            ob = proxy
            ob.manage_afterCMFAdd(ob, container)
            self._insertWorkflow(ob, initial_transition, initial_behavior,
                                 kwargs)
        else:
            raise NotImplementedError(initial_behavior)
        return ob

    def _insertWorkflow(self, ob, initial_transition, initial_behavior,
                        kwargs):
        """Insert ob into workflows."""
        # Do initial transition for all workflows.
        LOG('_insertWorkflow', DEBUG,
            "inserting %s using transition=%s behavior=%s kw=%s" %
            (ob.getId(), initial_transition, initial_behavior, kwargs))
        reindex = 0
        for wf in self.getWorkflowsFor(ob):
            if hasattr(aq_base(wf), 'insertIntoWorkflow'):
                wf.insertIntoWorkflow(ob, initial_transition, initial_behavior,
                                      kwargs)
            reindex = 1
        if reindex:
            self._reindexWorkflowVariables(ob)

    def _insertWorkflowRecursive(self, ob, initial_transition,
                                 initial_behavior, kwargs):
        """Recursively insert into workflows.

        Only done for proxies... XXX correct?
        """
        LOG('_insertWorkflowRecursive', DEBUG,
            "Recursively inserting %s using transition=%s behavior=%s"
            % (ob.getId(), initial_transition, initial_behavior))
        if not _isinstance(ob, ProxyBase):
            LOG('_insertWorkflowRecursive', DEBUG, "  Is not a proxy")
            #return # XXX correct?
        self._insertWorkflow(ob, initial_transition, initial_behavior, kwargs)
        for subob in ob.objectValues():
            self._insertWorkflowRecursive(subob, initial_transition,
                                          initial_behavior, kwargs)

    security.declarePrivate('checkinObject')
    def checkinObject(self, ob, dest_ob, transition):
        """Checkin ob into dest_ob.

        Then make the dest_ob follow the transition.

        (Called by CPS Workflow during checkin transition.)
        """
        ok, why = self.isBehaviorAllowedFor(dest_ob, TRANSITION_ALLOW_CHECKIN,
                                            transition, get_details=1)
        if not ok:
            if why:
                details = 'not allowed by workflow %s' % why
            else:
                details = 'no workflow'
            raise WorkflowException("Object=%s transition=%s does not allow "
                                    "checkin behavior (%s)" %
                                    (dest_ob.getId(), transition, details))
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool.checkinRevisions(ob, dest_ob)
        self.doActionFor(dest_ob, transition)

    security.declarePrivate('mergeObject')
    def mergeObject(self, ob, dest_container, state_var, new_state):
        """Merge a proxy into some existing one.

        Merging is the act of adding the revisions of a proxy into an
        existing one in the same container.

        Returns the destination object, or None if no merging was found.

        Does not do deletion of the source object. The destination
        object is guaranteed to be different than the source.

        (Called by CPSWorkflow during merge transition.)
        """
        dest_ob = self._checkObjectMergeable(ob, dest_container,
                                             state_var, new_state)[0]
        if dest_ob is not None:
            pxtool = getToolByName(self, 'portal_proxies')
            pxtool.checkinRevisions(ob, dest_ob)
        return dest_ob

    security.declarePublic('isObjectMergeable')
    def isObjectMergeable(self, ob, dest_container, state_var, new_state):
        """Check if a proxy can be merged into some existing one
        in the destination container.

        dest_container can be an rpath.

        Returns the destination rpath, and language_revs, or None, None
        """
        dest_ob, language_revs = self._checkObjectMergeable(ob, dest_container,
                                                            state_var,
                                                            new_state)
        if dest_ob is not None:
            utool = getToolByName(self, 'portal_url')
            return utool.getRelativeUrl(dest_ob), language_revs
        else:
            return None, None

    security.declarePrivate('_checkObjectMergeable')
    def _checkObjectMergeable(self, ob, dest_container, state_var, new_state):
        """Check if a proxy can be merged into some existing one
        in the destination container.

        dest_container can be an rpath.

        Return the destination proxy and language_revs, or None, None.
        """
        LOG('_checkObjectMergeable', DEBUG,
            'check ob=%s dest=%s var=%s state=%s'
            % (ob.getId(), dest_container, state_var, new_state))
        if not _isinstance(ob, ProxyBase):
            LOG('_checkObjectMergeable', DEBUG, ' Not a proxy')
            return None, None

        utool = getToolByName(self, 'portal_url')
        pxtool = getToolByName(self, 'portal_proxies')

        rpath = utool.getRelativeUrl(ob)
        if isinstance(dest_container, StringType):
            container_rpath = dest_container
        else:
            container_rpath = utool.getRelativeUrl(dest_container)
        if container_rpath:
            container_rpath += '/'
        infos = pxtool.getProxyInfosFromDocid(ob.getDocid(),
                                              [state_var])
        dest_ob = None
        language_revs = None
        for info in infos:
            dob = info['object']
            drpath = info['rpath']
            if drpath != container_rpath+dob.getId():
                # Proxy not in the dest container.
                LOG('_checkObjectMergeable', DEBUG,
                    '  Not in dest: %s' % drpath)
                continue
            if info[state_var] != new_state:
                # Proxy not in the correct state.
                LOG('_checkObjectMergeable', DEBUG,
                    '  Bad state=%s: %s' % (info[state_var], drpath))
                continue
            if drpath == rpath:
                # Skip ourselves.
                LOG('_checkObjectMergeable', DEBUG,
                    '  Ourselves: %s' % drpath)
                continue
            # Get the first one that matches.
            dest_ob = dob
            language_revs = info['language_revs']
            LOG('_checkObjectMergeable', DEBUG, ' Found %s' % drpath)
            break
        if dest_ob is None:
            LOG('_checkObjectMergeable', DEBUG, ' NotFound')
        return dest_ob, language_revs

    #
    # Constrained workflow transitions for folderish documents.
    #
    security.declarePublic('doActionFor')
    def doActionFor(self, ob, action, wf_id=None, *args, **kw):
        """Execute the given workflow action for the object.

        Invoked by user interface code.
        The workflow object must perform its own security checks.
        """
        # Don't recurse for initial transitions! # XXX urgh
        isproxyfolderishdoc = _isinstance(ob, ProxyFolderishDocument)
        if isproxyfolderishdoc and not kw.has_key('dest_container'):
            return self._doActionForRecursive(ob, action, wf_id=wf_id,
                                              *args, **kw)
        else:
            return self._doActionFor(ob, action, wf_id=wf_id, *args, **kw)

    security.declarePrivate('_doActionFor')
    def _doActionFor(self, ob, action, wf_id=None, *args, **kw):
        """Follow a transition."""
        LOG('_doActionFor', DEBUG, 'start, ob=%s action=%s' %
            (ob.getId(), action))
        wfs = self.getWorkflowsFor(ob)
        if wfs is None:
            wfs = ()
        if wf_id is None:
            if not wfs:
                raise WorkflowException('No workflows found.')
            found = 0
            for wf in wfs:
                LOG('_doActionFor', DEBUG, ' testing wf %s' % wf.getId())
                if wf.isActionSupported(ob, action):
                    LOG('_doActionFor', DEBUG, ' found!')
                    found = 1
                    break
                LOG('_doActionFor', DEBUG, ' not found')
            if not found:
                raise WorkflowException(
                    'No workflow provides the "%s" action.' % action)
        else:
            wf = self.getWorkflowById(wf_id)
            if wf is None:
                raise WorkflowException(
                    'Requested workflow definition not found.')
        return self._invokeWithNotification(
            wfs, ob, action, wf.doActionFor, (ob, action) + args, kw)

    security.declarePrivate('_doActionForRecursive')
    def _doActionForRecursive(self, ob, action, wf_id=None, *args, **kw):
        """Recursively calls doactionfor."""
        LOG('_doActionForRecursive', DEBUG, 'ob=%s action=%s' %
            (ob.getId(), action))
        if not _isinstance(ob, ProxyBase): # XXX
            return
        self._doActionFor(ob, action, wf_id=wf_id, *args, **kw)
        for subob in ob.objectValues():
            self._doActionForRecursive(subob, action, wf_id=wf_id, *args, **kw)

    #
    # History/status management
    #

    security.declarePublic('getFullHistoryOf')
    def getFullHistoryOf(self, ob):
        """Return the full history of an object.

        Uses aggregated history for proxies.

        Returns () for non-proxies.
        """
        if not _checkPermission(View, ob):
            raise Unauthorized("Can't get history of an unreachable object.")
        if not _isinstance(ob, ProxyBase):
            return ()
        repotool = getToolByName(self, 'portal_repository')
        return repotool.getHistory(ob.getDocid()) or ()

    security.declarePrivate('setStatusOf')
    def setStatusOf(self, wf_id, ob, status):
        """Append an entry to the workflow history.

        Stores the local history in the object itself.
        Stores the aggregated history using the repository tool.

        The entry also has 'rpath' and 'workflow_id' values stored.

        Invoked by workflow definitions.
        """
        # Additional info in status: rpath, workflow_id
        repotool = getToolByName(self, 'portal_repository')
        utool = getToolByName(self, 'portal_url')
        status = status.copy()
        status['rpath'] = utool.getRelativeUrl(ob)
        status['workflow_id'] = wf_id
        # Standard CMF storage.
        WorkflowTool.setStatusOf(self, wf_id, ob, status)
        # Store aggregated history in repository.
        if not _isinstance(ob, ProxyBase):
            return
        docid = ob.getDocid()
        wfh = repotool.getHistory(docid) or ()
        wfh += (status,)
        repotool.setHistory(docid, wfh)

    #
    # Misc
    #

    # Overloaded for placeful workflow definitions
    def getChainFor(self, ob, container=None):
        """Return the chain that applies to the given object.

        The first argument is either an object or a portal type name.

        Takes into account placeful workflow definitions, by starting
        looking for them at the object itself, or in the container
        if provided.
        """
##         import traceback
##         from StringIO import StringIO
##         s = StringIO()
##         traceback.print_stack(file=s)
##         LOG('getChainFor', DEBUG, 'comming from tb:\n%s' % s.getvalue())

        if isinstance(ob, StringType):
            pt = ob
        elif hasattr(aq_base(ob), '_getPortalTypeName'):
            pt = ob._getPortalTypeName()
            if container is None:
                container = ob
        else:
            pt = None
        if pt is None:
            return ()
        if container is None:
            LOG('CPSWorkflowTool', ERROR,
                'getChainFor: no container for ob %s' % (ob,))
            return ()
        # Find placeful workflow configuration object.
        wfconf = getattr(container, CPSWorkflowConfig_id, None)
        if wfconf is not None:
            # Was it here or did we acquire?
            start_here = hasattr(aq_base(container), CPSWorkflowConfig_id)
            chain = wfconf.getPlacefulChainFor(pt, start_here=start_here)
            if chain is not None:
                return chain
        # Nothing placeful found.
        return self.getGlobalChainFor(pt)

    security.declarePrivate('getGlobalChainFor')
    def getGlobalChainFor(self, ob):
        """Get the global chain for a given object or type_name."""
        return CPSWorkflowTool.inheritedAttribute('getChainFor')(self, ob)

    security.declarePrivate('getManagedPermissions')
    def getManagedPermissions(self):
        """Get all the permissions managed by the workflows."""
        perms = {}
        for wf in self.objectValues():
            if not getattr(wf, '_isAWorkflow', 0):
                continue
            if hasattr(aq_base(wf), 'getManagedPermissions'):
                # CPSWorkflow
                permissions = wf.getManagedPermissions()
            elif hasattr(aq_base(wf), 'permissions'):
                # DCWorkflow
                permissions = wf.permissions
            else:
                # Probably a DefaultWorkflow
                permissions = (View, ModifyPortalContent)
            for p in permissions:
                perms[p] = None
        return perms.keys()

    #
    # ZMI
    #
    manage_overview = DTMLFile('zmi/explainCPSWorkflowTool', globals())

    def all_meta_types(self):
        return ({'name': 'CPS Workflow',
                 'action': 'manage_addWorkflowForm',
                 'permission': ManagePortal},
                {'name': 'Workflow',
                 'action': 'manage_addWorkflowForm',
                 'permission': ManagePortal},
                )


InitializeClass(CPSWorkflowTool)


def addCPSWorkflowTool(container, REQUEST=None):
    """Add a CPS Workflow Tool."""
    ob = CPSWorkflowTool()
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')
