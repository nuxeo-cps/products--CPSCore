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

from zLOG import LOG, INFO, DEBUG

#
# Monkey patching starts here
#
# Patching UndoTool: Removing undo action
#

from Products.CMFCore.UndoTool import UndoTool
import utils # To quickly force the patching of localroles.

_actions = []
UndoTool._actions = _actions
LOG("CPSCore", INFO, "Patching CMFCore UndoTool : removing undo action")

#
# UndoToolPatch  monkey patching ends here
#

from Products.CMFCore import utils as cmfutils
from Products.CMFCore.CMFCorePermissions import AddPortalContent, ManagePortal

# Don't remove.
import AllowModules

#import ElementsTool
import EventServiceTool
import EventServicePatches
import TypesToolPatches
import PatchBTreeFolder2
#import LoggerTool
#import MirrorTool
import ProxyTool
import ObjectRepositoryTool
import CPSWorkflowTool
import TreesTool
import CPSMembershipTool

from CPSWorkflowConfiguration import CPSWorkflowConfiguration
from CPSWorkflowConfiguration import addCPSWorkflowConfiguration

import ProxyBase

# register CPSWorkflow
import CPSWorkflow


tools = (
    EventServiceTool.EventServiceTool,
#    LoggerTool.LoggerTool,
#    MirrorTool.MirrorTool,
#    ElementsTool.ElementsTool,
    ProxyTool.ProxyTool,
    ObjectRepositoryTool.ObjectRepositoryTool,
    CPSWorkflowTool.CPSWorkflowTool,
    TreesTool.TreesTool,
    CPSMembershipTool.CPSMembershipTool
)

contentClasses = (ProxyBase.ProxyFolder,
                  ProxyBase.ProxyDocument,
                  ProxyBase.ProxyFolderishDocument,
                  )

contentConstructors = (ProxyBase.addProxyFolder,
                       ProxyBase.addProxyDocument,
                       ProxyBase.addProxyFolderishDocument,
                       CPSMembershipTool.addCPSMembershipTool
                       )

fti = (ProxyBase.factory_type_information +
       ())

def initialize(registrar):
    cmfutils.ToolInit(
        'CPS Tools',
        tools=tools,
        product_name='CPSCore',
        icon='tool.gif',
    ).initialize(registrar)

    # Elements
    #registrar.registerClass(
    #    ElementsTool.DefaultElement,
    #    permission='Add a Default Element',
    #    constructors=(
    #        ElementsTool.ElementsTool.manage_addDefaultElement,
    #    )
    #)

    # Event Service
    registrar.registerClass(
        EventServiceTool.SubscriberDef,
        permission='Add a Subscriber Definition',
        constructors=(
            EventServiceTool.EventServiceTool.manage_addSubscriber,
        )
    )

    # Workflow Configuration Object
    registrar.registerClass(
        CPSWorkflowConfiguration,
        permission=ManagePortal,
        constructors=(addCPSWorkflowConfiguration,)
    )

    # Tree Cache
    registrar.registerClass(
        TreesTool.TreeCache,
        permission=ManagePortal,
        constructors=(TreesTool.TreesTool.manage_addCPSTreeCache,)
    )
    cmfutils.registerIcon(TreesTool.TreeCache, 'zmi/tree_icon.gif', globals())

    
    # CPS Content and Folder objects
    cmfutils.ContentInit(
        'CPS Default Documents',
        content_types=contentClasses,
        permission=AddPortalContent,
        extra_constructors=contentConstructors,
        fti=fti,
    ).initialize(registrar)
