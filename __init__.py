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

# Elements
import ElementsTool

# Event Service
import EventServiceTool
import LoggerTool
import MirrorTool

tools = (
    EventServiceTool.EventServiceTool,
    LoggerTool.LoggerTool,
    MirrorTool.MirrorTool,
    ElementsTool.ElementsTool,
)

registerDirectory('skins', globals())

# XXX this patches should be in the same place
# Some patches so classical zope actions send notifications

class FakeEventService:
    def notify(self, *args, **kw):
        pass

fake_event_service = FakeEventService()

def patch_action(class_, action):
    old_action = 'old_' + action
    if hasattr(class_, old_action):
        ok = "Old action already there"
    else:
        old = getattr(class_, action)
        setattr(class_, 'old_' + action, old)
        ok = 'Done'
    new = eval(action)
    setattr(class_, action, new)
    LOG('EventService', INFO, 'patch %s.%s... %s' % \
        (class_.__name__, action, ok))

def notify(self, event_type, object, *args, **kw):
    evtool = utils.getToolByName(self, 'portal_eventservice', fake_event_service)
    infos = {
        'args': args,
        'kw': kw,
    }
    evtool.notify(event_type, object, infos)

def manage_afterAdd(self, *args, **kw):
    """manage_afterAdd patched
    """
    notify(self, 'add_object', self, *args, **kw)
    self.old_manage_afterAdd(*args, **kw)

def manage_beforeDelete(self, *args, **kw):
    """manage_beforeDelete patched
    """
    self.old_manage_beforeDelete(*args, **kw)
    notify(self, 'del_object', self, *args, **kw)

from OFS.ObjectManager import ObjectManager
from OFS.SimpleItem import Item

patch_action(ObjectManager, 'manage_afterAdd')
patch_action(Item, 'manage_afterAdd')
patch_action(ObjectManager, 'manage_beforeDelete')
patch_action(Item, 'manage_beforeDelete')

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
