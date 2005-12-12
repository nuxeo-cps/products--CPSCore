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
from Products.CPSCore.IndexationManager import IndexationManager
from Products.CPSCore.IndexationManager import get_indexation_manager

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

    def _reindexObject(self, idxs=[]):
        self.log.append('idxs %s %r' % (self.id, idxs))

    def _reindexObjectSecurity(self, skip_self=False):
        self.log.append('secu %s %r' % (self.id, skip_self))


class Dummy2(Dummy):

    def _reindexObject(self, idxs=[]):
        if idxs == ['nest']:
            # While reindexing, provoke another indexing
            get_indexation_manager().push(self, idxs=['bob'])
            get_indexation_manager().push(self.other, idxs=['bob'])
        Dummy._reindexObject(self, idxs)


class IndexationManagerTest(unittest.TestCase):

    def get_stuff(self):
        return IndexationManager(FakeTransactionManager()), root.addDummy()

    def test_z2interfaces(self):
        from Interface.Verify import verifyClass
        verifyClass(IBaseManager, IndexationManager)

    def test_fixtures(self):

        mgr, dummy = self.get_stuff()

        self.assertEqual(mgr._sync, False)
        self.assertEqual(mgr.isSynchronous(), False)
        self.assertEqual(mgr.isSynchronous(), mgr._sync)
        self.assertEqual(mgr._status, True)

    def test_simple(self):
        mgr, dummy = self.get_stuff()

        # Push it, reindexation not done yet.
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])

        # Manager is called (by commit), check reindexation is done.
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

        # Object is gone from queue after that.
        mgr()
        self.assertEquals(dummy.getLog(), [])

        root.clear()

    def test_several_times_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['a'])
        mgr.push(dummy, idxs=['b'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['a', 'b']"%dummy.id])
        root.clear()

    def test_several_times_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])
        root.clear()

    def test_several_times_3(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])
        root.clear()

    def test_several_times_4(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id])
        root.clear()

    def test_several_times_5(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id])
        root.clear()

    def test_several_times_6(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])
        root.clear()

    def test_several_times_7(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])
        root.clear()

    def test_several_secu_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id,
                                           "secu %s False"%dummy.id])
        root.clear()

    def test_several_secu_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id,
                                           "secu %s True"%dummy.id])
        root.clear()

    def test_several_secu_3(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['allowedRolesAndUsers'])
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(),
                          ["idxs %s ['allowedRolesAndUsers', 'foo']"%dummy.id,
                           "secu %s True"%dummy.id])
        root.clear()

    def test_synchronous(self):
        mgr, dummy = self.get_stuff()
        self.assertEquals(dummy.getLog(), [])
        mgr.push(dummy, idxs=['a'])
        self.assertEquals(dummy.getLog(), [])
        mgr.setSynchronous(True)
        self.assertEquals(dummy.getLog(), ["idxs %s ['a']"%dummy.id])
        mgr.push(dummy, idxs=['b'])
        self.assertEquals(dummy.getLog(), ["idxs %s ['b']"%dummy.id])
        mgr.push(dummy, idxs=['c'])
        self.assertEquals(dummy.getLog(), ["idxs %s ['c']"%dummy.id])
        mgr.setSynchronous(False)
        mgr.push(dummy, idxs=['d'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['d']"%dummy.id])
        root.clear()

    def test_status_api(self):

        mgr, dummy = self.get_stuff()

        self.assertEqual(mgr._status, True)
        mgr.disable()
        self.assertEqual(mgr._status, False)
        mgr.enable()
        self.assertEqual(mgr._status, True)

    def test_status_with_async_subscriber(self):

        mgr, dummy = self.get_stuff()

        # Disable the subsriber
        mgr.disable()

        # Push it, reindexation not done yet because async. The push is
        # not supposed to do anything anyway here since the subscriber
        # is disabled

        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])

        # Manager is called (by commit).
        mgr()
        self.assertEquals(dummy.getLog(), [])

        # Object is gone from queue after that.
        mgr()
        self.assertEquals(dummy.getLog(), [])

        # Enable the subsriber
        mgr.enable()

        # Push it, reindexation not done yet because async. The push is
        # not supposed to do anything anyway here since the subscriber
        # is disabled

        mgr.push(dummy, idxs=[])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

        # Object is gone from queue after that.
        mgr()
        self.assertEquals(dummy.getLog(), [])

        root.clear()

    def test_status_with_sync_subscriber(self):

        mgr, dummy = self.get_stuff()

        # Set the subcriber async mode to True
        mgr.setSynchronous(True)

        # Disable the subsriber
        mgr.disable()

        # Push it, reindexation not done yet because async. The push is
        # not supposed to do anything anyway here since the subscriber
        # is disabled

        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])

        # Enable the subsriber
        mgr.enable()

        # Push it, reindexation not done yet because async. The push is
        # not supposed to do anything anyway here since the subscriber
        # is disabled

        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

        # Object is gone from queue after that.
        self.assertEquals(dummy.getLog(), [])

        root.clear()

class TransactionIndexationManagerTest(unittest.TestCase):

    # These really test the beforeCommitHook

    def test_transaction(self):
        transaction.begin()
        mgr = get_indexation_manager()
        dummy = root.addDummy()
        mgr.push(dummy, idxs=['bar'])
        self.assertEquals(dummy.getLog(), [])
        transaction.commit()
        self.assertEquals(dummy.getLog(), ["idxs %s ['bar']"%dummy.id])
        root.clear()

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_indexation_manager()
        dummy = root.addDummy()
        mgr.push(dummy, idxs=['bar'])
        self.assertEquals(dummy.getLog(), [])
        transaction.abort()
        self.assertEquals(dummy.getLog(), [])
        root.clear()

    def test_transaction_nested(self):
        transaction.begin()
        mgr = get_indexation_manager()
        # This one, when reindexed, provokes additional reindexings,
        # which must be processed too.
        dummy = root.addDummy(cls=Dummy2)
        other = root.addDummy()
        dummy.other = other
        mgr.push(dummy, idxs=['nest'])
        self.assertEquals(dummy.getLog(), [])
        self.assertEquals(other.getLog(), [])
        transaction.commit()
        self.assertEquals(dummy.getLog(), ["idxs %s ['nest']" % dummy.id,
                                           "idxs %s ['bob']" % dummy.id])
        self.assertEquals(other.getLog(), ["idxs %s ['bob']" % other.id])
        root.clear()


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(IndexationManagerTest),
        unittest.makeSuite(TransactionIndexationManagerTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
