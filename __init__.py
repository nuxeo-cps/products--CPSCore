# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Jalon <jj@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
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

from zLOG import LOG, DEBUG, TRACE

#
# Monkey patching starts here
#

# Remove the overflow pb when using a DateIndex for expires
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl
from DateTime.DateTime import DateTime
DefaultDublinCoreImpl._DefaultDublinCoreImpl__CEILING_DATE = DateTime(3000, 0)


#
# Patching UndoTool: Removing undo action
#

from Products.CMFCore.UndoTool import UndoTool
import utils # To quickly force the patching of localroles.

_actions = []
UndoTool._actions = _actions
LOG("CPSCore", TRACE, "Patching CMFCore UndoTool : removing undo action")


from Products.CMFCore import utils as cmfutils
from Products.CMFCore.permissions import AddPortalContent, ManagePortal

# Don't remove.
import AllowModules

import EventServiceTool
import EventServicePatches
import TypesToolPatches
import PatchBTreeFolder2
import PatchCatalogTool
import PatchCMFCatalogAware
import ProxyTool
import ObjectRepositoryTool
import TreesTool
import CPSMembershipTool
import CPSRegistrationTool
import OrderedFolderSupportPatch
import CopyrightPatch

import ProxyBase

tools = (
    EventServiceTool.EventServiceTool,
    ProxyTool.ProxyTool,
    ObjectRepositoryTool.ObjectRepositoryTool,
    TreesTool.TreesTool,
    CPSMembershipTool.CPSMembershipTool,
    CPSRegistrationTool.CPSRegistrationTool,
)

contentClasses = (ProxyBase.ProxyFolder,
                  ProxyBase.ProxyDocument,
                  ProxyBase.ProxyFolderishDocument,
                  ProxyBase.ProxyBTreeFolder,
                  ProxyBase.ProxyBTreeFolderishDocument,
                  )

contentConstructors = (ProxyBase.addProxyFolder,
                       ProxyBase.addProxyDocument,
                       ProxyBase.addProxyFolderishDocument,
                       ProxyBase.addProxyBTreeFolder,
                       ProxyBase.addProxyBTreeFolderishDocument,
                       CPSMembershipTool.addCPSMembershipTool,
                       CPSRegistrationTool.addCPSRegistrationTool,
                       )

fti = (ProxyBase.factory_type_information +
       ())

def initialize(registrar):
    cmfutils.ToolInit(
        'CPS Tools',
        tools=tools,
        product_name='CPSCore',
        icon='tool.png',
    ).initialize(registrar)

    # Event Service
    registrar.registerClass(
        EventServiceTool.SubscriberDef,
        permission='Add a Subscriber Definition',
        constructors=(
            EventServiceTool.EventServiceTool.manage_addSubscriber,
        )
    )

    # Tree Cache
    registrar.registerClass(
        TreesTool.TreeCache,
        permission=ManagePortal,
        constructors=(TreesTool.TreesTool.manage_addCPSTreeCache,)
    )
    cmfutils.registerIcon(TreesTool.TreeCache, 'zmi/tree_icon.png', globals())

    # CPS Content and Folder objects
    cmfutils.ContentInit(
        'CPS Default Documents',
        content_types=contentClasses,
        permission=AddPortalContent,
        extra_constructors=contentConstructors,
        fti=fti,
    ).initialize(registrar)
