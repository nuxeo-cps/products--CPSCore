# (Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""Patch CMFCore CMFCatalogAware

- Make reindexObjectSecurity correctly recurse in the presence of
  'viewLanguage' brains.
"""
from Acquisition import aq_base
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware


def reindexObjectSecurity(self, skip_self=False):
    """
        Reindex security-related indexes on the object
        (and its descendants).
    """
    catalog = getToolByName(self, 'portal_catalog', None)
    if catalog is not None:
        path = '/'.join(self.getPhysicalPath())
        for brain in catalog.unrestrictedSearchResults(path=path):
            brain_path = brain.getPath()
            if brain_path == path and skip_self:
                continue

            # Get the object
            if hasattr(aq_base(brain), '_unrestrictedGetObject'):
                ob = brain._unrestrictedGetObject()
            else: # BBB: older Zope
                ob = self.unrestrictedTraverse(brain_path)
            s = getattr(ob, '_p_changed', 0)
            # Recatalog with the same catalog uid.
            catalog.catalog_object(ob, brain_path,
                                   idxs=self._cmf_security_indexes,
                                   update_metadata=0)
            if s is None: ob._p_deactivate()

CMFCatalogAware.reindexObjectSecurity = reindexObjectSecurity
