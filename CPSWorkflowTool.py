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
"""Workflow Tool with CPS proxy knowledge and CPS placeful workflow support.
"""

from zLOG import LOG, ERROR, DEBUG
from types import StringType
from Acquisition import aq_base, aq_parent, aq_inner
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo, Unauthorized

from Products.CMFCore.utils import getToolByName, _checkPermission
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFCore.WorkflowTool import WorkflowTool


CPSWorkflowConfig_id = '.cps_workflow_configuration'


class CPSWorkflowTool(WorkflowTool):
    """A Workflow Tool extending the CMFCore one with CPS features.

    - Creation transition knowledge for CPSWorkflow
    - Placefulness

    A creation transition is the fact that an object created in a workflow
    can be created according to several transitions into its initial
    state. This choice must be available to the user.
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
    # API
    #

    security.declarePublic('isCreationAllowedIn')
    def isCreationAllowedIn(self, container, get_details=0):
        """Is the creation of a subobject allowed in the container? """
        wf_ids = self.getChainFor(container)
        for wf_id in wf_ids:
            wf = self.getWorkflowById(wf_id)
            if not hasattr(aq_base(wf), 'isCreationAllowedIn'):
                # Not a CPS workflow.
                continue
            ok, why = wf.isCreationAllowedIn(container, get_details=1)
            if not ok:
                if get_details:
                    return 0, '%s, %s' % (wf_id, why)
                else:
                    return 0
        if get_details:
            return 1, ''
        else:
            return 1

    security.declarePublic('getCreationTransitions')
    def getCreationTransitions(self, container, type_name):
        """Get the possible creation transitions in a container.

        Returns a dict of {wf_id: [sequence of transitions]}.
        Raises WorkflowException if a non-CPS workflow is encountered.
        """
        wf_ids = self.getChainFor(type_name, container=container)
        creation_transitions = {}
        for wf_id in wf_ids:
            wf = self.getWorkflowById(wf_id)
            if not hasattr(aq_base(wf), 'getCreationTransitions'):
                # Not a CPS workflow.
                continue
            transitions = wf.getCreationTransitions(container)
            creation_transitions[wf_id] = transitions
        return creation_transitions

    security.declarePublic('invokeFactoryFor')
    def invokeFactoryFor(self, container, type_name, id,
                         creation_transitions={},
                         *args, **kw):
        """Create an object in a container.

        The variable creation_transitions is a dict of {wf_id:
        transition}, it is used to decide initial transitions in the
        object's workflows.

        The object created will be a proxy to a real object if the type
        type_name has an action of id 'isproxytype' and of action
        'folder' or 'document'.
        """
        LOG('invokeFactoryFor', DEBUG, 'Called with container=%s type_name=%s '
            'id=%s creation_transitions=%s' % (container.getId(), type_name,
                                               id, creation_transitions))
        # Check that the workflows of the container allow subobject creation.
        ok, why = self.isCreationAllowedIn(container, get_details=1)
        if not ok:
            if why:
                details = 'not allowed by workflow %s' % why
            else:
                details = 'no workflow'
            raise WorkflowException("Container %s does not allow "
                                    "subobject creation (%s)" %
                                    (container.getId(), details))
        # Find the transitions to use.
        allowed = self.getCreationTransitions(container, type_name)
        use_transitions = {}
        for wf_id, transitions in allowed.items():
            if not creation_transitions.has_key(wf_id):
                if not transitions:
                    raise WorkflowException(
                        "Workflow %s does not allow creation of %s"
                        % (wf_id, type_name))
                # Use first default if nothing specified
                # XXX parametrize this default ?
                transition = transitions[0]
            else:
                transition = creation_transitions.get(wf_id)
                if transition not in transitions:
                    raise WorkflowException(
                        "Workflow %s cannot create %s using transition %s"
                        % (wf_id, type_name, transition))
            use_transitions[wf_id] = transition
        # Find out if we must create a normal document or a proxy.
        # XXX determine what's the best way to parametrize this
        proxy_type = None
        ttool = getToolByName(self, 'portal_types')
        for ti in ttool.listTypeInfo():
            if ti.getId() != type_name:
                continue
            proxy_type = ti.getActionById('isproxytype', None)
            if proxy_type is not None:
                break
        # Creation.
        if proxy_type is not None:
            # Create a proxy and a document in the repository.
            pxtool = getToolByName(self, 'portal_proxies')
            ob = pxtool.createProxy(proxy_type, container, type_name, id,
                                    *args, **kw)
        else:
            # Create a normal CMF document.
            # Note: this calls wf.notifyCreated() for all wf!
            container.invokeFactoryCMF(type_name, id, *args, **kw)
            # XXX should get new id effectively used! CMFCore bug!
            ob = container[id]
        # Do creation transitions for all workflows.
        reindex = 0
        for wf_id, transition in use_transitions.items():
            wf = self.getWorkflowById(wf_id)
            wf.notifyCreated(ob, creation_transition=transition)
            reindex = 1
        if reindex:
            self._reindexWorkflowVariables(ob)
        return id

    security.declarePublic('getCloneAllowedTransitions')
    def getCloneAllowedTransitions(self, ob, tid):
        """Get the list of allowed initial transitions for clone."""
        res = []
        wf_ids = self.getChainFor(ob)
        for wf_id in wf_ids:
            wf = self.getWorkflowById(wf_id)
            if not hasattr(aq_base(wf), 'getCloneAllowedTransitions'):
                # Not a CPS workflow.
                continue
            allowed = wf.getCloneAllowedTransitions(ob, tid)
            res.extend([t for t in allowed if t not in res])
        return res

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
        if isinstance(ob, StringType):
            pt = ob
        elif hasattr(aq_base(ob), '_getPortalTypeName'):
            pt = ob._getPortalTypeName()
            if container is None:
                #container = aq_parent(aq_inner(ob))
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
            chain = wfconf.getPlacefulChainFor(pt)
            if chain is not None:
                return chain
        # Nothing placeful found.
        return self.getGlobalChainFor(pt)

    security.declarePrivate('getGlobalChainFor')
    def getGlobalChainFor(self, ob):
        """Get the global chain for a given object or type_name."""
        return CPSWorkflowTool.inheritedAttribute('getChainFor')(self, ob)

    #
    # ZMI
    #

    manage_overview = DTMLFile('zmi/explainCPSWorkflowTool', globals())


InitializeClass(CPSWorkflowTool)


def addCPSWorkflowTool(container, REQUEST=None):
    """Add a CPS Workflow Tool."""
    ob = CPSWorkflowTool()
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')
