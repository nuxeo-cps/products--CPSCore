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

from Products.CPSCore.interfaces import IBeforeCommitSubscriber
from Products.CPSCore.TreeCacheManager import TreeCacheManager
from Products.CPSCore.TreeCacheManager import get_treecache_manager

from Products.CPSCore.treemodification import ADD

import transaction

class FakeBeforeCommitSubscribersManager:
    def addSubscriber(self, hook, order):
        pass

class DummyTreeCache(SimpleItem):
    notified = 0
    def updateTree(self, tree):
        self.notified += 1


class TreeCacheManagerTest(unittest.TestCase):

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        verifyClass(IBeforeCommitSubscriber, TreeCacheManager)

    def test_fixtures(self):

        mgr = TreeCacheManager(FakeBeforeCommitSubscribersManager())
                
        self.assertEqual(mgr._sync, False)
        self.assertEqual(mgr.isSynchronous(), False)
        self.assertEqual(mgr.isSynchronous(), mgr._sync)
        self.assertEqual(mgr.enabled, True)

    def test_status_api(self):

        mgr = TreeCacheManager(FakeBeforeCommitSubscribersManager())

        self.assertEqual(mgr.enabled, True)
        mgr.disable()
        self.assertEqual(mgr.enabled, False)
        mgr.enable()
        self.assertEqual(mgr.enabled, True)

    def test_simple(self):
        mgr = TreeCacheManager(FakeBeforeCommitSubscribersManager())
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

    def test_status_with_async_subscriber(self):

        mgr = TreeCacheManager(FakeBeforeCommitSubscribersManager())
        cache = DummyTreeCache()

        self.assertEqual(mgr.enabled, True)
        self.assertEqual(mgr._sync, False)

        # Disable subscriber
        mgr.disable()

        # Push it, reindexation not done yet.
        mgr.push(cache, ADD, ('abc',), None)
        mgr.push(cache, ADD, ('def',), None)
        mgr.push(cache, ADD, ('ghi',), None)
        self.assertEquals(cache.notified, 0)

        # Manager is called (by commit), check notification
        mgr()
        self.assertEquals(cache.notified, 0)

        # Nothing left after that
        mgr()
        self.assertEquals(mgr._trees, {})

        # Enable subscriber back
        mgr.enable()

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
