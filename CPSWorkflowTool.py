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


class CPSWorkflowTool(WorkflowTool):
    """A Workflow Tool extending the CMFCore one with CPS features.

    - Creation transition knowledge for CPSWorkflow
    - Placefulness

    A creation transition is the fact that an object created in a workflow
    can be created according to several transitions in to their initial
    state. This choice must be available to the user.
    """

    id = 'portal_workflow'
    meta_type = 'CPS Workflow Tool'

    security = ClassSecurityInfo()

    #def __init__(self):
    #    pass

    #
    # API
    #

    security.declarePublic('getCreationTransitions')
    def getCreationTransitions(self, container, portal_type):
        """Get the possible creation transitions in a container.

        Returns a dict of {wf_id: sequence_of_transitions}.
        """
        # XXX
        # - get the allowed workflows in this container
        wfs = self.getWorkflowsForContainer(container, portal_type)
        creation_transitions = {}
        for wf in wfs:
            creation_transitions[wf.getId()] = ['_create'] # XXX
        return creation_transitions
        #return {'workflow_foo': ['submit', 'publish'],
        #        'workflow_bar': [],
        #        }


    security.declarePublic('invokeFactoryFor')
    def invokeFactoryFor(self, container, portal_type, id,
                         creation_transitions={},
                         *args, **kw):
        """Create an object in a container.

        creation_transitions is a dict of {wf_id: transition}.
        It is used to decide initial transitions in the object's workflows.
        """
        if not _checkPermission(AddPortalContent, container):
            raise Unauthorized
        possible_transitions = self.getCreationTransitions(container,
                                                           portal_type)
        for wf_id, transition in creation_transitions.items():
            if transition not in possible_transitions.get(wf_id, []):
                raise WorkflowException(
                    "No workflow allows the creation of %s using %s" %
                    (portal_type, creation_transitions))
        # calls wf.notifyCreated!
        container.invokeFactory(portal_type, id, *args, **kw)
        # XXX should get new id effectively used! CMFCore bug!
        ob = container[id]
        for wf_id, transitions in possible_transitions.items():
            transition = creation_transitions.get(wf_id)
            if transition is None:
                # use first default
                if not transitions:
                    raise WorkflowException(
                        "Workflow %s does not allow creation" % (wf_id,))
                transition = transitions[0]
            wf = self.getWorkflowById(wf_id)
            if wf is None:
                raise WorkflowException("%s is not a workflow id" % (wf_id,))
            wf.doActionFor(ob, transition)
        return id

    # overloaded
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
            LOG('CPSWorkflowTool', DEBUG,
                'getChainFor: no container for ob %s' % (ob,))
            return ()

        # XXX not placeful for now
        return WorkflowTool.inheritedAttribute('getChainFor')(self, pt)

    #
    # ZMI
    #

    manage_overview = DTMLFile('zmi/explainCPSWorkflowTool', globals())


InitializeClass(CPSWorkflowTool)
