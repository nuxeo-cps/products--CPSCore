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

from Products.CPSCore.IndexationManager import IndexationManager
from Products.CPSCore.IndexationManager import get_indexation_manager
from Products.CPSCore.IndexationManager import ACTION_INDEX
from Products.CPSCore.IndexationManager import ACTION_UNINDEX
from Products.CPSCore.IndexationManager import ACTION_REINDEX

import transaction

class FakeTransaction:
    def addBeforeCommitHook(self, hook):
        pass

class FakeBeforeCommitSubscribersManager:
    def addSubscriber(self, hook, order):
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
        return self.getContent(int(id))

    def addContent(self, cls=None):
        id = self.generateId()
        if cls is None:
            cls = FakeContent
        ob = cls(id)
        self.__objects__[id] = ob
        return ob

    def getContent(self, id):
        return self.__objects__.get(id)

    def clear(self):
        self.__objects__ = {}

root = FakeRoot()


class FakeCatalog:
    """Does uncataloging by redirection to object, to allow logging stuff."""

    def unindexObject(self, ob):
        ob.unindex()

    def unindexCPSObjectWithPath(self, ob, path):
        ob.unindex(path=path)


class FakeContent:

    portal_catalog = FakeCatalog()

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

    def unindex(self, path=None):
        """Specific of FakeContent"""
        msg = 'Unindex %s' % self.id
        if path is not None:
            msg += ' path=' + path
        self.log.append(msg)


class FakeContentCausingReindex(FakeContent):

    def _reindexObject(self, idxs=[]):
        if idxs == ['nest']:
            # While reindexing, provoke another indexing
            get_indexation_manager().push(self, idxs=['bob'])
            get_indexation_manager().push(self.other, idxs=['bob'])
        FakeContent._reindexObject(self, idxs)


class IndexationManagerTest(unittest.TestCase):

    def tearDown(self):
        root.clear()

    def get_stuff(self):
        return (IndexationManager(FakeBeforeCommitSubscribersManager()),
                root.addContent())

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        from Products.CPSCore.interfaces import IBeforeCommitSubscriber
        verifyClass(IBeforeCommitSubscriber, IndexationManager)

    def test_fixtures(self):

        mgr, dummy = self.get_stuff()

        self.assertEqual(mgr._sync, False)
        self.assertEqual(mgr.isSynchronous(), False)
        self.assertEqual(mgr.isSynchronous(), mgr._sync)
        self.assertEqual(mgr.enabled, True)

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

    def test_unindex(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, action=ACTION_UNINDEX)
        mgr()
        did = dummy.id
        self.assertEquals(dummy.getLog(), ['Unindex %s path=/%s' % (did, did)])
        mgr()
        self.assertEquals(dummy.getLog(), [])

    def test_several_times_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['a'])
        mgr.push(dummy, idxs=['b'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['a', 'b']"%dummy.id])

    def test_several_times_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

    def test_several_times_3(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

    def test_several_times_4(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id])

    def test_several_times_5(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id])

    def test_several_times_6(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

    def test_several_times_7(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id])

    def test_several_secu_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s ['foo']"%dummy.id,
                                           "secu %s False"%dummy.id])

    def test_several_secu_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs %s []"%dummy.id,
                                           "secu %s True"%dummy.id])

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

    def test_index_unindex(self):
        # index + unindex == nothing to do
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[], action=ACTION_INDEX)
        mgr.push(dummy, action=ACTION_UNINDEX)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), [])

    def test_reindex_unindex(self):
        # index + unindex == unindex
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[], action=ACTION_REINDEX)
        mgr.push(dummy, action=ACTION_UNINDEX)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        did = dummy.id
        self.assertEquals(dummy.getLog(), ["Unindex %s path=/%s" % (did,did)],)

    def test_index_reindex_unindex(self):
        # index + reindex + unindex == nothing to do
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[], action=ACTION_INDEX)
        mgr.push(dummy, idxs=[], action=ACTION_REINDEX)
        mgr.push(dummy, action=ACTION_UNINDEX)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), [])

    def test_unindex_index(self):
        # unindex + index = reindex (full)
        # this is to get (unindex + index) + unindex = unindex
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, action=ACTION_UNINDEX)
        mgr.push(dummy, idxs=['foo'], action=ACTION_INDEX)
        infos = mgr._infos
        self.assertEquals(len(infos), 1)
        self.assertEquals(infos.values()[0]['action'], ACTION_REINDEX)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ['idxs %s []' % dummy.id])

    def test_unindex_reindex(self):
        # unindex + reindex = reindex (full)
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, action=ACTION_UNINDEX)
        mgr.push(dummy, idxs=['foo'], action=ACTION_REINDEX)
        infos = mgr._infos
        self.assertEquals(len(infos), 1)
        self.assertEquals(infos.values()[0]['action'], ACTION_REINDEX)

        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ['idxs %s []' % dummy.id])

    def test_unindex_reindex_secu(self):
        # unindex + reindex = reindex (full)
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, action=ACTION_UNINDEX)
        mgr.push(dummy, idxs=['foo'], action=ACTION_REINDEX, with_security=True)
        infos = mgr._infos
        self.assertEquals(len(infos), 1)
        self.assertEquals(infos.values()[0]['action'], ACTION_REINDEX)

        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ['idxs %s []' % dummy.id,
                                           "secu %s True" %dummy.id])

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

    def test_enabled_api(self):

        mgr, dummy = self.get_stuff()

        self.assertEqual(mgr.enabled, True)
        mgr.disable()
        self.assertEqual(mgr.enabled, False)
        mgr.enable()
        self.assertEqual(mgr.enabled, True)

    def test_enabled_with_async_subscriber(self):

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

    def test_enabled_with_sync_subscriber(self):

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

class TransactionIndexationManagerTest(unittest.TestCase):

    # These really test the beforeCommitHook

    def test_transaction(self):
        transaction.begin()
        mgr = get_indexation_manager()
        dummy = root.addContent()
        mgr.push(dummy, idxs=['bar'])
        self.assertEquals(dummy.getLog(), [])
        transaction.commit()
        self.assertEquals(dummy.getLog(), ["idxs %s ['bar']"%dummy.id])
        root.clear()

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_indexation_manager()
        dummy = root.addContent()
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
        dummy = root.addContent(cls=FakeContentCausingReindex)
        other = root.addContent()
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
