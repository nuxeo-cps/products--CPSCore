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
from Products.CMFCore.CMFCorePermissions import AddPortalContent
from Products.CMFCore.WorkflowTool import WorkflowTool

from Products.NuxCPS3.CPSWorkflowConfiguration import CPSWorkflowConfiguration_id



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

    security.declarePublic('getCreationTransitions')
    def getCreationTransitions(self, container, type_name):
        """Get the possible creation transitions in a container.

        Returns a dict of {wf_id: sequence_of_transitions}.
        The sequence is None for non-CPS workflows (meaning that
        a default state will be used).
        """
        wf_ids = self.getChainFor(type_name, container=container)
        creation_transitions = {}
        for wf_id in wf_ids:
            wf = self.getWorkflowById(wf_id)
            if hasattr(aq_base(wf), 'getCreationTransitions'):
                transitions = wf.getCreationTransitions(container)
            else:
                # Not a CPS Workflow.
                transitions = None
            creation_transitions[wf.getId()] = transitions
        return creation_transitions

    security.declarePublic('invokeFactoryFor')
    def invokeFactoryFor(self, container, type_name, id,
                         creation_transitions={},
                         *args, **kw):
        """Create an object in a container.

        creation_transitions is a dict of {wf_id: transition}.
        It is used to decide initial transitions in the object's workflows.
        """
        if not _checkPermission(AddPortalContent, container):
            raise Unauthorized
        allowed = self.getCreationTransitions(container, type_name)
        # Check that all requested transitions are available.
        for wf_id, transition in creation_transitions.items():
            transitions = allowed.get(wf_id)
            if transitions is None:
                # Non-CPS workflow.
                raise WorkflowException(
                    "Workflow %s cannot have creation transitions" % (wf_id,))
            if transition not in transitions:
                raise WorkflowException(
                    "Workflow %s cannot create %s using transition '%s'" %
                    (wf_id, type_name, transition))
        # calls wf.notifyCreated()!
        container.invokeFactory(type_name, id, *args, **kw)
        # XXX should get new id effectively used! CMFCore bug!
        ob = container[id]
        # Do creation transitions for all workflows.
        reindex = 0
        for wf_id, transitions in allowed.items():
            transition = creation_transitions.get(wf_id)
            if transition is None:
                # Use first default.
                # XXX parametrize default ?
                if not transitions:
                    raise WorkflowException(
                        "Workflow %s does not allow creation" % (wf_id,))
                transition = transitions[0]
            wf = self.getWorkflowById(wf_id)
            if wf is None:
                raise WorkflowException("%s is not a workflow id" % (wf_id,))
            wf.notifyCreated(ob, creation_transition=transition)
            reindex = 1
        if reindex:
            self._reindexWorkflowVariables(ob)
        return id

    # Overloaded for placeful workflow definitions
    def getChainFor(self, ob, container=None):
        """Return the chain that applies to the given object.

        The first argument is either an object or a portal type name.
        Takes into account placeful workflow definitions.
        """
        if isinstance(ob, StringType):
            pt = ob
        elif hasattr(aq_base(ob), '_getPortalTypeName'):
            pt = ob._getPortalTypeName()
            if container is None:
                container = aq_parent(aq_inner(ob))
        else:
            pt = None
        if pt is None:
            return ()
        if container is None:
            LOG('CPSWorkflowTool', ERROR,
                'getChainFor: no container for ob %s' % (ob,))
            return ()
        # Find placeful workflow configuration object.
        wfconf = getattr(container, CPSWorkflowConfiguration_id, None)
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
