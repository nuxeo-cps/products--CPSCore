# -*- coding: iso-8859-15 -*-
# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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

"""Workflow Stack Definition interface

This module contains the interface for the WorkflowStackDefinition class
"""

import Interface

class IWorkflowStackDefinition(Interface.Base):
    """API for the Workflow Stack Definition
    """

    def getStackDataStructureType():
        """Returns the id of the stack data structure the stack definition is
        hodling
        """

    def getStackWorkflowVariableId():
        """Returns the workflow variable id mapping this configuration
        """

    def getAssociatedLocalRole():
        """Returns the workflow variable id mapping this configuration
        """

    def getGrantedLocalRolesForManage():
        """Returns the local roles granted to manage the stack.
        It's in use when the stack is not initialized yet
        """

    def push(ds, **kw):
        """Push delegatees

        This method has to be implemented by a child class
        """

    def pop(ds, **kw):
        """Pop delegatees

        This method has to be implemented by a child class
        """

    def canManageStack(ds, aclu, mtool, context, **kw):
        """Can the current member manage the stack ?

        It will depend on the stack data structure.
        """

    def listLocalRoles(ds):
        """Give the local roles mapping for the member / group ids within the
        stack
        """

    def getFormerLocalRolesMapping(ds):
        """Give the former local roles mapping for the member / group ids
        within the stack
        """

    def isLocked():
        """Is the stack locked
        """

    def doLockStack():
        """Lock the stack
        """

    def doUnLockStack():
        """UnLock stack
        """

    def getManagerStackIds():
        """Returns the ids of other stacks for which the people within those
        can manage this stack. For instance in the common use case members
        within the 'Pilots' stack can manage 'Associates' and 'Watchers'
        stacks.
        """

    def resetStack(ds, **kw):
        """Reset stack.

        ds contains the data structure.
        """
