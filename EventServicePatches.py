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
"""Patch Zope so that it sends standard notifications.
"""

from zLOG import LOG, DEBUG

from Products.NuxCPS3.EventServiceTool import getEventService


def notify(self, event_type, object, *args, **kw):
    evtool = getEventService(self)
    infos = {'args': args, 'kw': kw}
    evtool.notify(event_type, object, infos)

def manage_afterAdd(self, *args, **kw):
    """manage_afterAdd patched for event service notification."""
    notify(self, 'sys_add_object', self, *args, **kw)
    self.cps_old_manage_afterAdd(*args, **kw)

def manage_beforeDelete(self, *args, **kw):
    """manage_beforeDelete patched for event service notification."""
    self.cps_old_manage_beforeDelete(*args, **kw)
    notify(self, 'sys_del_object', self, *args, **kw)

def manage_afterClone(self, *args, **kw):
    """manage_afterClone patched for event service notification."""
    self.cps_old_manage_afterClone(*args, **kw)
    notify(self, 'sys_clone_object', self, *args, **kw)

def move_object_to_position(self, *args, **kw):
    res = self.cps_old_move_object_to_position(*args, **kw)
    notify(self, 'sys_order_object', self, *args, **kw)
    return res

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
    LOG('EventService', DEBUG, ('patching %s.%s... %s' %
                               (class_.__name__, action, ok)))

from OFS.ObjectManager import ObjectManager
from OFS.SimpleItem import Item
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

for class_ in (Item, ObjectManager, CMFCatalogAware):
    patch_action(class_, manage_afterAdd)
    patch_action(class_, manage_beforeDelete)
    patch_action(class_, manage_afterClone)


import Products.OrderedFolderSupportPatch # ensure it does its patches

patch_action(ObjectManager, move_object_to_position)
