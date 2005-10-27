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

try:
    import transaction
except ImportError: # BBB: for Zope 2.7
    from Products.CMFCore.utils import transaction


class FakeTransaction:
    def addBeforeCommitHook(self, hook):
        pass

class FakeTransactionManager:
    def addBeforeCommitHook(self, hook, order):
        pass

class FakeRoot:
    __objects__ = {}

    def generateId(self):
        id = random.randrange(1000000)
        while id in self.__objects__.keys():
            id = random.randrange(1000000)
        return id

    def unrestrictedTraverse(self, path, default):
        dummy, id = path
        assert dummy == ''
        return self.getDummy(int(id))

    def addDummy(self, cls=None):
        id = self.generateId()
        if cls is None:
            cls = Dummy
        ob = cls(id)
        self.__objects__[id] = ob
        return ob

    def getDummy(self, id):
        return self.__objects__.get(id)

    def clear(self):
        self.__objects__ = {}

root = FakeRoot()

class Dummy:
    def __init__(self, id):
        self.id = id
        self.log = []

    def getLog(self):
        # get and clear log
        log = self.log
        self.log = []
        return log

    def getPhysicalRoot(self):
        return root

    def getPhysicalPath(self):
        return ('', str(self.id))

class DummyTreeCache(SimpleItem):
    notified = 0
    def notify_tree(self, event_type, ob, infos):
        self.notified = self.notified + 1
    def _isCandidate(self, ob, plen):
        return True


class TreeCacheManagerTest(unittest.TestCase):

    def get_stuff(self):
        return (TreeCacheManager(FakeTransactionManager()),
                root.addDummy(),
                DummyTreeCache())

    def test_z2interfaces(self):
        from Interface.Verify import verifyClass
        verifyClass(IBaseManager, TreeCacheManager)

    def test_simple(self):
        mgr, dummy, tree = self.get_stuff()

        # Push it, reindexation not done yet.
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)

        # Manager is called (by commit), check notification
        mgr()
        self.assertEquals(tree.notified, 1)

        # Object is gone from queue after that.
        mgr()
        self.assertEquals(mgr._queue, {})

        root.clear()

    def test_several_times_1(self):
        mgr, dummy, tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_2(self):
        mgr, dummy, tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        mgr.push(tree, 'sys_add_cmf_object', dummy, {'foo':'bar'})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_3(self):
        mgr, dummy, tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {'foo':'bar'})
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_4(self):
        mgr, dummy, tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {'foo':'bar'})
        mgr.push(tree, 'sys_add_cmf_object', dummy, None)
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_5(self):
        mgr, dummy,tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, None)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {'foo':'bar'})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_6(self):
        mgr, dummy,tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, None)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_times_7(self):
        mgr, dummy,tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        mgr.push(tree, 'sys_add_cmf_object', dummy, None)
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_several_events_1(self):
        # XXX : this is supposed to break when the optimizations will be done.
        # This is what I expect.
        mgr, dummy, tree = self.get_stuff()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        mgr.push(tree, 'sys_del_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        mgr()
        self.assertEquals(tree.notified, 2)
        root.clear()

    def test_synchronous(self):
        mgr, dummy, tree = self.get_stuff()
        self.assertEquals(tree.notified, 0)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        mgr.setSynchronous(True)
        self.assertEquals(tree.notified, 1)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 2)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 3)
        mgr.setSynchronous(False)
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 3)
        mgr()
        self.assertEquals(tree.notified, 4)
        root.clear()

class TreeCacheManagerIntegrationTest(unittest.TestCase):

    # These really test the beforeCommitHook

    def test_transaction(self):
        transaction.begin()
        mgr = get_treecache_manager()
        tree = DummyTreeCache()
        dummy = root.addDummy()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        transaction.commit()
        self.assertEquals(tree.notified, 1)
        root.clear()

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_treecache_manager()
        tree = DummyTreeCache()
        dummy = root.addDummy()
        mgr.push(tree, 'sys_add_cmf_object', dummy, {})
        self.assertEquals(tree.notified, 0)
        transaction.abort()
        self.assertEquals(tree.notified, 0)
        root.clear()

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreeCacheManagerTest),
        unittest.makeSuite(TreeCacheManagerIntegrationTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
