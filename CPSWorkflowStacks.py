# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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

"""Backward compatibility;  see Products.CPSWorkflow.basicstacks
"""

from Products.CPSWorkflow.stack import Stack as BaseStack
from Products.CPSWorkflow.basicstacks import *

from warnings import warn

warn( "The module, 'Products.CPSCore.CPSWorkflowStacks' "
      "is a deprecated "
      "compatiblity alias for 'Products.CPSWorkflow.basicstacks';"
      "please use "
      "the new module instead.", DeprecationWarning)
