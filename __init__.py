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

import ElementsTool
import EventServiceTool
import EventServicePatches
import LoggerTool
import MirrorTool
import ProxyTool
import ObjectRepository
import CPSWorkflowTool

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

registerDirectory('skins', globals())

def initialize(registrar):
    utils.ToolInit(
        'CPS 3 Tools',
        tools = tools,
        product_name = 'NuxCPS3',
        icon = 'tool.gif',
    ).initialize(registrar)

    # Elements
    registrar.registerClass(
        ElementsTool.DefaultElement,
        permission='Add a Default Element',
        constructors=(
            ElementsTool.ElementsTool.manage_addDefaultElement,
        )
    )

    # Event Service
    registrar.registerClass(
        EventServiceTool.SubscriberDef,
        permission='Add a Subscriber Definition',
        constructors=(
            EventServiceTool.EventServiceTool.manage_addSubscriber,
        )
    )
