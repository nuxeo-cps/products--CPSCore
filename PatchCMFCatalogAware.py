# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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
"""Patch the CMFCore.CMFCatalogAware

The idea in here is to prevent the repository objects to be indexed
and add event service notifications 
""" 

from zLOG import LOG, DEBUG

from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

# XXX those patch can't be there as manage_XXXs are already defined over there
from Products.CPSCore.EventServicePatches import patch_action, notify

def manage_afterAdd(self, *args, **kw):
    """manage_afterAdd patched

       o for event service notification.
       o for repository objects

    """
    notify(self, 'sys_add_object', self, *args, **kw)
    if not 'portal_repository' in self.getPhysicalPath():
        self._cps_old_manage_afterAdd(*args, **kw)

def manage_beforeDelete(self, *args, **kw):
    """manage_beforeDelete patched for

      o event service notification.
      o for repository objects

    """
    if not 'portal_repository' in self.getPhysicalPath():
        self._cps_old_manage_beforeDelete(*args, **kw)
    notify(self, 'sys_del_object', self, *args, **kw)

patch_action(CMFCatalogAware, manage_afterAdd)
patch_action(CMFCatalogAware, manage_beforeDelete)

LOG('PatchCMFCatalogAware', DEBUG, 'Patched')
