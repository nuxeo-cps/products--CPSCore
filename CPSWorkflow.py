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
from Acquisition import aq_base
from Globals import InitializeClass, PersistentMapping
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName

from Products.CMFCore.WorkflowCore import ObjectDeleted, ObjectMoved
from Products.CMFCore.WorkflowTool import addWorkflowFactory

from Products.DCWorkflow.DCWorkflow import DCWorkflowDefinition


UNCREATED_STATE = 'uncreated_'


class CPSWorkflowDefinition(DCWorkflowDefinition):
    """A Workflow implementation with proxy support.

    Features:
    - Creation transitions (those from the uncreated_ state)
    - Extended transition description
    """

    meta_type = 'CPS Workflow'
    title = 'CPS Workflow Definition'

    security = ClassSecurityInfo()

    def manage_afterAdd(self, item, container):
        """Add special uncreated_ state after add."""
        if aq_base(self) is aq_base(item):
            if self.states.get(UNCREATED_STATE) is None:
                self.states.addState(UNCREATED_STATE)
                self.states.get(UNCREATED_STATE).title = 'Uncreated'
                #self.states.setInitialState(UNCREATED_STATE)
        DCWorkflowDefinition.inheritedAttribute('manage_afterAdd')(
            self, item, container)

    #
    # API
    #

    security.declarePrivate('getCreationTransitions')
    def getCreationTransitions(self):
        """Get the possible creation transitions.

        A creation transition is a transition from the uncreated_ state.
        """
        creation_state = self.states.get(UNCREATED_STATE)
        if creation_state is None:
            return ()
        return tuple(creation_state.getTransitions())


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')
