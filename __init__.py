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

import Products.CPSCompat

#
# Monkey patching starts here
#

import utils # To quickly force the patching of localroles.

from Products.CMFCore import utils as cmfutils
from Products.CMFCore.permissions import AddPortalContent, ManagePortal

# Don't remove.
import AllowModules

# Patches
import PatchCMFCore
import CopyrightPatch

import EventServiceTool
import EventServicePatches
import ProxyTool
import ObjectRepositoryTool
import TreesTool
import CPSRegistrationTool
import URLTool
from Products.CPSCore.setuptool import CPSSetupTool

import ProxyBase

tools = (
    EventServiceTool.EventServiceTool,
    ProxyTool.ProxyTool,
    ObjectRepositoryTool.ObjectRepositoryTool,
    TreesTool.TreesTool,
    CPSRegistrationTool.CPSRegistrationTool,
    URLTool.URLTool,
    CPSSetupTool,
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
                       CPSRegistrationTool.addCPSRegistrationTool,
                       )

fti = (ProxyBase.factory_type_information +
       ())

def initialize(registrar):
    cmfutils.ToolInit(
        'CPS Tools',
        tools=tools,
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
