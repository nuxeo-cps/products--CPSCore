# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# (C) Copyright 2001 iuveno AG
# Authors: Florent Guillaume <fg@nuxeo.com>
#          Encolpe DEGOUTE <ed@nuxeo.com>
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
"""
  OrderedFolderSupportPatches.
  Monkey-patches ObjectManager to provide ordered folder behavior.
"""

from AccessControl.PermissionRole import PermissionRole
from Products.CPSCore.CPSCorePermissions import ChangeSubobjectsOrder

# derived from OrderFolder by Stephan Richter, iuveno AG.

from OFS.ObjectManager import ObjectManager

try:
     import Products.OrderedFolderSupportPatch
except ImportError:
     pass
else:
     raise ImportError("OrderedFolderSupportPatch is not compatible with this version of CPS")

# will be inserted into ObjectManager

def get_object_position(self, id):
    i = 0
    for obj in self._objects:
        if obj['id'] == id:
            return i
        i = i+1
    # If the object was not found, throw an error.
    raise 'ObjectNotFound', 'The object with the id "%s" does not exist.' % id

def move_object_to_position(self, id, newpos):
    oldpos = self.get_object_position(id)
    if (newpos < 0 or newpos == oldpos or newpos >= len(self._objects)):
        return 0
    obj = self._objects[oldpos]
    objects = list(self._objects)
    del objects[oldpos]
    objects.insert(newpos, obj)
    self._objects = tuple(objects)
    return 1

def move_object_up(self, id):
    newpos = self.get_object_position(id) - 1
    return self.move_object_to_position(id, newpos)

def move_object_down(self, id):
    newpos = self.get_object_position(id) + 1
    return self.move_object_to_position(id, newpos)

def move_object_to_top(self, id):
    newpos = 0
    return self.move_object_to_position(id, newpos)

def move_object_to_bottom(self, id):
    newpos = len(self._objects) - 1
    return self.move_object_to_position(id, newpos)


# will extend those in ObjectManager

def manage_renameObject(self, id, new_id, REQUEST=None):
    """Rename a particular sub-object"""
    #Since OFS.CopySupport.CopyContainer::manage_renameObject uses
    #_setObject manually, we have to take care of the order after it is done.
    oldpos = self.get_object_position(id)
    res = self._old_ordfold_manage_renameObject(id, new_id, REQUEST)
    self.move_object_to_position(new_id, oldpos)
    return res

def _setObject(self, id, object, roles=None, user=None, set_owner=1, \
               position=None):
    res = self._old_ordfold_setObject(id, object, roles, user, set_owner)
    if position is not None:
         self.move_object_to_position(id, position)
    # otherwise it was inserted at the end
    return res


# patch the class

ObjectManager.get_object_position = get_object_position
ObjectManager.move_object_to_position = move_object_to_position
ObjectManager.move_object_up = move_object_up
ObjectManager.move_object_down = move_object_down
ObjectManager.move_object_to_top = move_object_to_top
ObjectManager.move_object_to_bottom = move_object_to_bottom
# security
ObjectManager.get_object_position__roles__ = PermissionRole(ChangeSubobjectsOrder)
ObjectManager.move_object_to_position__roles__ = PermissionRole(ChangeSubobjectsOrder)
ObjectManager.move_object_up__roles__ = PermissionRole(ChangeSubobjectsOrder)
ObjectManager.move_object_down__roles__ = PermissionRole(ChangeSubobjectsOrder)
ObjectManager.move_object_to_top__roles__ = PermissionRole(ChangeSubobjectsOrder)
ObjectManager.move_object_to_bottom__roles__ = PermissionRole(ChangeSubobjectsOrder)

# Otherweise when it's refreshed the _setObject is calling itself recursively
# Zope.2.7.x
if not hasattr(ObjectManager, '_old_ordfold_setObject'):
     ObjectManager._old_ordfold_setObject = ObjectManager._setObject
if not hasattr(ObjectManager, '_old_ordfold_manage_renameObject'):
     ObjectManager._old_ordfold_manage_renameObject = ObjectManager.inheritedAttribute(
          'manage_renameObject')

ObjectManager.manage_renameObject = manage_renameObject
ObjectManager._setObject = _setObject

