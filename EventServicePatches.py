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
from Acquisition import aq_base
from Products.NuxCPS3.EventServiceTool import getEventService


def notify(context, event_type, object, *args, **kw):
    evtool = getEventService(context)
    infos = {'args': args, 'kw': kw}
    evtool.notify(event_type, object, infos)

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

#
# OFS
#

from OFS.ObjectManager import ObjectManager
from OFS.SimpleItem import Item
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

def manage_afterAdd(self, *args, **kw):
    """manage_afterAdd patched for event service notification."""
    notify(self, 'sys_add_object', self, *args, **kw)
    self.cps_old_manage_afterAdd(*args, **kw)

def manage_beforeDelete(self, *args, **kw):
    """manage_beforeDelete patched for event service notification."""
    self.cps_old_manage_beforeDelete(*args, **kw)
    notify(self, 'sys_del_object', self, *args, **kw)

for class_ in (Item, ObjectManager, CMFCatalogAware):
    patch_action(class_, manage_afterAdd)
    patch_action(class_, manage_beforeDelete)

#
# OrderedFolderSupportPatch
#

import Products.OrderedFolderSupportPatch # ensure it does its patches

def move_object_to_position(self, *args, **kw):
    res = self.cps_old_move_object_to_position(*args, **kw)
    notify(self, 'sys_order_object', self, *args, **kw)
    return res

patch_action(ObjectManager, move_object_to_position)

#
# Generators of CMF Add events
#

# The recursing method

def manage_afterCMFAdd(self, item, container):
    """Notify object and event service of CMF add finalization."""
    notify(self, 'sys_add_cmf_object', self)
    self._CMFCatalogAware__recurse('manage_afterCMFAdd', item, container)

CMFCatalogAware.manage_afterCMFAdd = manage_afterCMFAdd

# manage_renameObject

def manage_renameObject(self, id, new_id, REQUEST=None):
    res = self.cps_old_manage_renameObject(id, new_id, REQUEST=REQUEST)
    ob = self._getOb(new_id)
    if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
        ob.manage_afterCMFAdd(ob, self)
    return res

patch_action(ObjectManager, manage_renameObject)

# manage_pasteObjects

from OFS.CopySupport import CopyContainer
from OFS.CopySupport import CopyError, eNoData, eInvalid, _cb_decode
from OFS.CopySupport import cookie_path

def manage_pasteObjects(self, cb_copy_data=None, REQUEST=None):
    """Paste an object from a cut or copy."""
    # --- Get cp for the call and op for the cleanup
    cp=None
    if cb_copy_data is not None:
        cp=cb_copy_data
    else:
        if REQUEST and REQUEST.has_key('__cp'):
            cp=REQUEST['__cp']
    if cp is None:
        raise CopyError, eNoData
    try:    dcp=_cb_decode(cp)
    except: raise CopyError, eInvalid
    op = dcp[0]
    # --- call
    result = self.cps_old_manage_pasteObjects(cb_copy_data=cp)
    # --- send events
    for idchange in result:
        new_id = idchange['new_id']
        ob = self._getOb(new_id)
        if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
            ob.manage_afterCMFAdd(ob, self)
    # --- cleanup
    if op==0:
        if REQUEST is not None:
            return self.manage_main(self, REQUEST, update_menu=1,
                                    cb_dataValid=1)
    if op==1:
        if REQUEST is not None:
            REQUEST['RESPONSE'].setCookie('__cp', 'deleted',
                                path='%s' % cookie_path(REQUEST),
                                expires='Wed, 31-Dec-97 23:59:59 GMT')
            REQUEST['__cp'] = None
            return self.manage_main(self, REQUEST, update_menu=1,
                                    cb_dataValid=0)
    return result

patch_action(CopyContainer, manage_pasteObjects)

# manage_clone

def manage_clone(self, ob, id, REQUEST=None):
    # Clone an object.
    ob = self.cps_old_manage_clone(ob, id, REQUEST=REQUEST)
    if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
        ob.manage_afterCMFAdd(ob, self)
    return self

patch_action(CopyContainer, manage_clone)

# XXX _importObjectFromFile

