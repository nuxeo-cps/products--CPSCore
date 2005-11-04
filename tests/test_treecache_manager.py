# -*- coding: iso-8859-15 -*-
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
"""Tests for the Indexation Manager
"""

import random
import unittest
from OFS.SimpleItem import SimpleItem

from Products.CPSCore.interfaces import IBaseManager
from Products.CPSCore.TreeCacheManager import TreeCacheManager
from Products.CPSCore.TreeCacheManager import get_treecache_manager

from Products.CPSCore.treemodification import ADD


try:
    import transaction
except ImportError: # BBB: for Zope 2.7
    from Products.CMFCore.utils import transaction


class FakeTransactionManager:
    def addBeforeCommitHook(self, hook, order):
        pass

class DummyTreeCache(SimpleItem):
    notified = 0
    def updateTree(self, tree):
        self.notified += 1


class TreeCacheManagerTest(unittest.TestCase):

    def test_z2interfaces(self):
        from Interface.Verify import verifyClass
        verifyClass(IBaseManager, TreeCacheManager)

    def test_simple(self):
        mgr = TreeCacheManager(FakeTransactionManager())
        cache = DummyTreeCache()

        # Push it, reindexation not done yet.
        mgr.push(cache, ADD, ('abc',), None)
        mgr.push(cache, ADD, ('def',), None)
        mgr.push(cache, ADD, ('ghi',), None)
        self.assertEquals(cache.notified, 0)

        # Manager is called (by commit), check notification
        mgr()
        self.assertEquals(cache.notified, 1)

        # Nothing left after that
        mgr()
        self.assertEquals(mgr._trees, {})


class TreeCacheManagerIntegrationTest(unittest.TestCase):
    # These really test the beforeCommitHook

    def test_transaction(self):
        transaction.begin()
        mgr = get_treecache_manager()
        cache = DummyTreeCache()
        mgr.push(cache, ADD, ('abc',), None)
        self.assertEquals(cache.notified, 0)
        transaction.commit()
        self.assertEquals(cache.notified, 1)

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_treecache_manager()
        cache = DummyTreeCache()
        mgr.push(cache, ADD, ('abc',), None)
        self.assertEquals(cache.notified, 0)
        transaction.abort()
        self.assertEquals(cache.notified, 0)

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreeCacheManagerTest),
        unittest.makeSuite(TreeCacheManagerIntegrationTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
