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

"""Hierarchical Workflow Stack interface

This module contains the interface for the HierarchicalWorkflowStack class
"""

import Interface

class IHierarchicalWorkflowStack(Interface.Base):
    """API for the Hierarchical Workflow Stack
    """

    def __deepcopy__(ob):
        """Deep copy. Just to call a clean API while calling getCopy()
        """

    def getDirection():
        """Get the direction.
        """

    def setDirectionDown():
        """Set the direction below
        """

    def setDirectionUp():
        """Set the directionn above
        """

    def blockDirection():
        """Intermediate situation in between the 1 and 0
        """

    def returnedUpDirection():
        """Returned up direction
        """

    def getCurrentLevel():
        """Return the current level
        """

    def doIncLevel():
        """Increment the level value

        The level has to exist and host elts
        """

    def doDecLevel():
        """Decrement the level value

        The level has to exist and host elts
        """

    def getLevelContent(level=None):
        """Return  the content of the level given as parameter

        If not specified let's return the current level content
        """

    def getAllLevels():
        """Return all the existing levels with elts

        It's returned sorted
        """
