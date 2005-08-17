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
# Patch mergedLocalRoles to use aclu mergedLocalRoles if any
#
from Products.CMFCore import utils
from utils import mergedLocalRoles

LOG('PatchCMFCore.utils', INFO,
    'CPSCore Patch mergedLocalRoles to use aclu')
utils.mergedLocalRoles = mergedLocalRoles
utils._mergedLocalRoles = mergedLocalRoles


#############################################################
# Patch TypesTool so that TypeInformation's properties are editable.
#
import TypesToolPatches               # XXX rename into PatchCMFCoreTypesTool


#############################################################
# Patching CatalogTool to handle proxies search
#
import PatchCatalogTool               # XXX rename into PatchCMFCoreCatalogTool


#############################################################
# Patching UndoTool to remove undo action
#
from Products.CMFCore.UndoTool import UndoTool

LOG('PatchCMFCore.UndoTool', INFO,
    'CPSCore Patch _actions to remove undo action')
_actions = []
UndoTool._actions = _actions

#############################################################
# Patching PortalFolder._checkId to allow overrides of names starting
# with '.' at the root of the portal
#

from Acquisition import aq_parent, aq_inner
from AccessControl import getSecurityManager

from Products.CMFCore.exceptions import BadRequest
from Products.CMFCore.permissions import ManagePortal
from Products.CMFCore.PortalFolder import PortalFolderBase
from Products.CMFCore.PortalFolder import PortalFolder

if True:
    def _checkId(self, id, allow_dup=0):
        PortalFolderBase.inheritedAttribute('_checkId')(self, id, allow_dup)

        if allow_dup:
            return

        # FIXME: needed to allow index_html for join code
        if id == 'index_html':
            return

        # Another exception: Must allow "syndication_information" to enable
        # Syndication...
        if id == 'syndication_information':
            return

        # This code prevents people other than the portal manager from
        # overriding skinned names and tools.
        if not getSecurityManager().checkPermission(ManagePortal, self):
            ob = self
            while ob is not None and not getattr(ob, '_isPortalRoot', False):
                ob = aq_parent( aq_inner(ob) )
            if ob is not None:
                # If the portal root has a non-contentish object by this name,
                # don't allow an override.
                if (hasattr(ob, id) and
                    id not in ob.contentIds() and
                    not id.startswith('.')):
                    raise BadRequest('The id "%s" is reserved.' % id)
        # Otherwise we're ok.

PortalFolder._checkId = _checkId

LOG('PatchCMFCore.PortalFolder', INFO,
    'CPSCore Patch PortalFolder._checkId')



