# (c) 2002-2003 Nuxeo SARL <http://nuxeo.com/>
# (c) 2002-2003 Julien Jalon <mailto:jj@nuxeo.com>
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

from zLOG import LOG, INFO

from Acquisition import aq_base
from Products.CMFCore import utils
from Products.CMFCore.DirectoryView import registerDirectory
from Products.CMFCore.CMFCorePermissions import AddPortalContent

import ElementsTool
import EventServiceTool
import EventServicePatches
import LoggerTool
import MirrorTool
import ProxyTool
import ObjectRepository
import CPSWorkflowTool
from CPSWorkflowConfiguration import CPSWorkflowConfiguration
from CPSWorkflowConfiguration import addCPSWorkflowConfiguration

import ProxyBase
import CPSFolder
import CPSDummyDocument


# register CPSWorkflow
import CPSWorkflow


tools = (
    EventServiceTool.EventServiceTool,
    LoggerTool.LoggerTool,
    MirrorTool.MirrorTool,
    ElementsTool.ElementsTool,
    ProxyTool.ProxyTool,
    ObjectRepository.ObjectRepository,
    CPSWorkflowTool.CPSWorkflowTool,
)

contentClasses = (CPSFolder.CPSFolder,
                  CPSDummyDocument.CPSDummyDocument,
                  ProxyBase.ProxyFolder,
                  ProxyBase.ProxyDocument,
                  )

contentConstructors = (CPSFolder.addCPSFolder,
                       CPSDummyDocument.addCPSDummyDocument,
                       ProxyBase.addProxyFolder,
                       ProxyBase.addProxyDocument,
                       )

fti = (CPSFolder.factory_type_information +
       CPSDummyDocument.factory_type_information +
       ProxyBase.factory_type_information +
       ())

registerDirectory('skins', globals())

def initialize(registrar):
    utils.ToolInit(
        'CPS Tools',
        tools = tools,
        product_name = 'NuxCPS3',
        icon = 'tool.gif',
    ).initialize(registrar)

    # Elements
    registrar.registerClass(
        ElementsTool.DefaultElement,
        permission='Add a Default Element',
        constructors=(
            # XXX should not use an unbound method as a factory !!!
            ElementsTool.ElementsTool.manage_addDefaultElement,
        )
    )

    # Event Service
    registrar.registerClass(
        EventServiceTool.SubscriberDef,
        permission='Add a Subscriber Definition',
        constructors=(
            # XXX should not use an unbound method as a factory !!!
            EventServiceTool.EventServiceTool.manage_addSubscriber,
        )
    )

    # Workflow Configuration Object
    registrar.registerClass(
        CPSWorkflowConfiguration,
        permission='Manager portal',
        constructors=(addCPSWorkflowConfiguration,)
    )

    # CPS Content and Folder objects
    utils.ContentInit(
        'CPS Default Documents',
        content_types = contentClasses,
        permission = AddPortalContent,
        extra_constructors = contentConstructors,
        fti = fti,
        ).initialize(registrar)
