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

"""Simple Workflow Stack interface

This module contains the interface for the SimpleWorkflowStack class
"""

import Interface

class ISimpleWorkflowStack(Interface.Base):
    """API for the Workflow Stack
    """

    def __deepcopy__(ob):
        """Deep copy. Just to call a clean API while calling getCopy()
        """

    def removeElement(element=None):
        """Remove a given element

        O : failed
        1 : sucsess
        """
    def getStackContent(level=None):
        """Return the stack content
        """

    def getCopy():
        """Duplicate self

        Return a new object instance of the same type
        """
