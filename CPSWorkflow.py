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
from Globals import InitializeClass
from Globals import PersistentMapping
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName

from Products.CMFCore.WorkflowCore import ObjectDeleted, ObjectMoved
from Products.CMFCore.WorkflowTool import addWorkflowFactory

from Products.DCWorkflow.DCWorkflow import DCWorkflowDefinition


class CPSWorkflowDefinition(DCWorkflowDefinition):
    """A Workflow implementation with proxy support.

    Features:
    - Creation states
    - Extended transition description
    """

    meta_type = 'CPS Workflow'
    title = 'CPS Workflow Definition'

    security = ClassSecurityInfo()

    #
    # API
    #

    security.declarePrivate('getCreationTransitions')
    def getCreationTransitions(self):
        """Get the possible creation transitions."""
        # XXX
        return ['_create']

    # overloaded
    def notifyCreated(self, ob):
        """Notify this workflow after an object has been created
        and put in its new place.

        This does nothing.
        Actual workflow insertion is done through doActionFor.
        """
        pass

    # overloaded
    def isActionSupported(self, ob, action):
        sdef = self._getWorkflowStateOf(ob)
        if sdef is None:
            # not in a workflow
            if action == '_create': # XXX use real creation transitions
                return 1
            return 0
        return DCWorkflowDefinition.inheritedAttribute('isActionSupported')(
            self, ob, action)

    # overloaded
    def doActionFor(self, ob, action, **kw):
        """Do a workflow transition."""
        if action == '_create':
            # XXX temporary
            return self._changeStateOf(ob, None)
        return DCWorkflowDefinition.inheritedAttribute('doActionFor')(
            self, ob, action, **kw)


InitializeClass(CPSWorkflowDefinition)

addWorkflowFactory(CPSWorkflowDefinition, id='cps_workflow',
                   title='Web-configurable workflow for CPS')
