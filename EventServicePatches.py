# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
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

from zLOG import LOG, INFO

from Products.NuxCPS3.EventServiceTool import getEventService

# XXX this patches should be in the same place
# Some patches so classical zope actions send notifications

def notify(self, event_type, object, *args, **kw):
    evtool = getEventService(self)
    infos = {'args': args, 'kw': kw}
    evtool.notify(event_type, object, infos)

def manage_afterAdd(self, *args, **kw):
    """manage_afterAdd patched for event service notification."""
    notify(self, 'add_object', self, *args, **kw)
    self.cps_old_manage_afterAdd(*args, **kw)

def manage_beforeDelete(self, *args, **kw):
    """manage_beforeDelete patched for event service notification."""
    self.cps_old_manage_beforeDelete(*args, **kw)
    notify(self, 'del_object', self, *args, **kw)

def manage_afterClone(self, *args, **kw):
    """manage_afterClone patched for event service notification."""
    self.cps_old_manage_afterClone(*args, **kw)
    notify(self, 'clone_object', self, *args, **kw)


from OFS.ObjectManager import ObjectManager
from OFS.SimpleItem import Item

def patch_action(class_, func):
    action = func.__name__
    old_action = 'cps_old_%s' % action
    if hasattr(class_, old_action):
        ok = "Already patched."
    else:
        old = getattr(class_, action)
        setattr(class_, old_action, old)
        ok = 'Done.'
    setattr(class_, action, func)
    LOG('EventService', INFO, ('patching %s.%s... %s' %
                               (class_.__name__, action, ok)))

patch_action(ObjectManager, manage_afterAdd)
patch_action(Item, manage_afterAdd)
patch_action(ObjectManager, manage_beforeDelete)
patch_action(Item, manage_beforeDelete)
patch_action(ObjectManager, manage_afterClone)
patch_action(Item, manage_afterClone)

