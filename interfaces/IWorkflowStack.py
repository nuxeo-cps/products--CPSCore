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

"""Workflow Stack interface

This module contains the interface for the WorkflowStack class
"""

import Interface

class IWorkflowStack(Interface.Base):
    """API for the Workflow Stack
    """

    def isFull():
        """Is the queue Full ?

        Used in the case of max size is specified
        """
    def isEmpty():
        """Is the Stack empty ?
        """

    def push(elt=None):
        """Push an element in the queue

        1  : ok
        0  : queue id full
        -1 : elt is None
        """

    def pop():
        """Get the first element of the queue

        0 : empty
        1 : ok
        """

    def getFormerLocalRolesMapping():
        """Return the former local roles mapping

        So that we can make diff and update local roles.
        """

    def setFormerLocalRolesMapping(mapping):
        """Set the former local roles mapping information

        So that we can make diff and update local roles.
        """

    def reset():
        """Reset the stack

        Simply Call the constructor to reinitialize
        """
