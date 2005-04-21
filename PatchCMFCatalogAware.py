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

from Products.CMFCore.utils import getToolByName
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


def reindexObjectSecurity(self, skip_self=False):
    """Reindex security-related indexes on the object (and its descendants).

    An optional argument skip_self can be passed, since it's useless to
    reindex the object itself if it has already been fully indexed.
    """

    catalog = getToolByName(self, 'portal_catalog', None)
    if catalog is not None:
        path = '/'.join(self.getPhysicalPath())
        try:
            brains = catalog.unrestrictedSearchResults(path=path)
        except AttributeError:
            # BBB: Old CMF
            brains = catalog.searchResults(path=path)
        for brain in brains:
            brain_path = brain.getPath()
            # self is treated at the end
            if brain_path == path:
                continue
            ob = self.unrestrictedTraverse(brain_path, None)
            if ob is None:
                # Ignore old references to deleted objects.
                continue
            s = getattr(ob, '_p_changed', 0)

            catalog.reindexObject(ob, idxs=['allowedRolesAndUsers'],
                                  update_metadata=0)
            if s is None: ob._p_deactivate()
        # Reindex the object itself, as the PathIndex only gave us
        # the descendants.
        if not skip_self:
            catalog.reindexObject(self, idxs=['allowedRolesAndUsers'],
                                  update_metadata=0)


patch_action(CMFCatalogAware, manage_afterAdd)
patch_action(CMFCatalogAware, manage_beforeDelete)
CMFCatalogAware.reindexObjectSecurity = reindexObjectSecurity

LOG('PatchCMFCatalogAware', DEBUG, 'Patched')
