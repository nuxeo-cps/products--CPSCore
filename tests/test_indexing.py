# -*- coding: iso-8859-15 -*-
# Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author: Florent Guillaume <fg@nuxeo.com>
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
"""Tests Indexing through the catalog.
"""

import random
import unittest
from Testing import ZopeTestCase

# Ensure we have made our patches
ZopeTestCase.installProduct('CPSCompat')
# Need patches for groups too
ZopeTestCase.installProduct('CPSUserFolder')

ZopeTestCase.installProduct('ZCTextIndex')


from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem

# We really test these, in interaction with CPS
from Products.CMFCore.CatalogTool import CatalogTool
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware


class Folder(Folder):
    def __init__(self, id):
        self._setId(id)

class Dummy(SimpleItem, CMFCatalogAware):
    def __init__(self, id):
        self._setId(id)

class CPSCatalogTool(CatalogTool):
    def enumerateIndexes(self):
        return CatalogTool.enumerateIndexes(self) + (
            ('localUsersWithRoles', 'KeywordIndex', None),
            )


class IndexingTest(unittest.TestCase):

    def setUp(self):
        self.root = Folder('')
        self.root.site = Folder('site')
        self.site = self.root.site
        self.site._setObject('portal_catalog', CPSCatalogTool())
        self.site.dummy = Dummy('dummy')

    def test_cmf_security_indexes(self):
        ok = ('allowedRolesAndUsers', 'localUsersWithRoles')
        self.assertEquals(self.site.dummy._cmf_security_indexes, ok)

    def test_reindex_security_indexes(self):
        # Check that our specific security-related index is reindexed by
        # reindexObjectSecurity.
        dummy = self.site.dummy
        cat = self.site.portal_catalog

        dummy.indexObject()
        res = cat.unrestrictedSearchResults()
        self.assertEquals(len(res), 1)
        res = cat.unrestrictedSearchResults(localUsersWithRoles='user:bob')
        self.assertEquals(len(res), 0)

        # Now add a local role
        dummy.manage_setLocalRoles('bob', ['Winner'])
        dummy.reindexObjectSecurity()
        res = cat.unrestrictedSearchResults(localUsersWithRoles='user:bob')
        self.assertEquals(len(res), 1)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(IndexingTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
