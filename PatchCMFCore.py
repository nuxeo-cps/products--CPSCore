# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""This file contains all patches for the CMFCore product."""

from zLOG import LOG, DEBUG, INFO, DEBUG


#############################################################
# Patching UndoTool to remove undo action
#
from Products.CMFCore.UndoTool import UndoTool

LOG('PatchCMFCore.UndoTool', INFO,
    'CPSCore Patch _actions to remove undo action')
_actions = []
UndoTool._actions = _actions



#############################################################
# Patching CatalogTool to handle proxies search
#
import PatchCatalogTool               # XXX rename into PatchCMFCoreCatalogTool


#############################################################
# This is a patch for CMFCore.Skinnable submitted by efge
# to fix the bug http://www.zope.org/Collectors/CMF/198/
#
# WARNING this patch is not compatible with Speedpack !

# this is the SkinnableObjectManager patch
import PatchCMFCoreSkinnableObjectManager

# this is the PortalObject patch
LOG('PatchCMFCore.PortalObject', INFO,
    'CPSCore Patching __getattr__ to fix CMFCore bug #198')

from Products.CMFCore.Skinnable import SkinnableObjectManager
from Products.CMFCore.PortalObject import PortalObjectBase

PortalObjectBase.__getattr__ = SkinnableObjectManager.__getattr__
PortalObjectBase._checkId = SkinnableObjectManager._checkId

LOG('PatchCMFCore.PortalObject', DEBUG, 'Patched')

