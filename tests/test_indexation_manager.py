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

import unittest
from OFS.SimpleItem import SimpleItem

from Products.CPSCore.IndexationManager import IndexationManager
from Products.CPSCore.IndexationManager import get_indexation_manager

class FakeTransaction:
    def beforeCommitHook(self, hook):
        pass

class Dummy:
    def __init__(self, id):
        self.id = id
        self.log = []

    def getLog(self):
        # get and clear log
        log = self.log
        self.log = []
        return log

    def _reindexObject(self, idxs=[]):
        self.log.append('idxs %s %r' % (self.id, idxs))

    def _reindexObjectSecurity(self, skip_self=False):
        self.log.append('secu %s %r' % (self.id, skip_self))


class IndexationManagerTest(unittest.TestCase):

    def get_stuff(self):
        return IndexationManager(FakeTransaction()), Dummy('dummy')

    def test_simple(self):
        mgr, dummy = self.get_stuff()

        # Push it, reindexation not done yet.
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])

        # Manager is called (by commit), check reindexation is done.
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []"])

        # Object is gone from queue after that.
        mgr()
        self.assertEquals(dummy.getLog(), [])

    def test_several_times_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['a'])
        mgr.push(dummy, idxs=['b'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['a', 'b']"])

    def test_several_times_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []"])

    def test_several_times_3(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []"])

    def test_several_times_4(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['foo']"])

    def test_several_times_5(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=['foo'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['foo']"])

    def test_several_times_6(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=None)
        mgr.push(dummy, idxs=[])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []"])

    def test_several_times_7(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, idxs=None)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []"])

    def test_several_secu_1(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['foo']",
                                           "secu dummy False"])

    def test_several_secu_2(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=[])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy []",
                                           "secu dummy True"])

    def test_several_secu_3(self):
        mgr, dummy = self.get_stuff()
        mgr.push(dummy, idxs=['allowedRolesAndUsers'])
        mgr.push(dummy, idxs=['foo'])
        mgr.push(dummy, with_security=True)
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(),
                          ["idxs dummy ['allowedRolesAndUsers', 'foo']",
                           "secu dummy True"])

    def test_synchronous(self):
        mgr, dummy = self.get_stuff()
        self.assertEquals(dummy.getLog(), [])
        mgr.push(dummy, idxs=['a'])
        self.assertEquals(dummy.getLog(), [])
        mgr.setSynchonous(True)
        self.assertEquals(dummy.getLog(), ["idxs dummy ['a']"])
        mgr.push(dummy, idxs=['b'])
        self.assertEquals(dummy.getLog(), ["idxs dummy ['b']"])
        mgr.push(dummy, idxs=['c'])
        self.assertEquals(dummy.getLog(), ["idxs dummy ['c']"])
        mgr.setSynchonous(False)
        mgr.push(dummy, idxs=['d'])
        self.assertEquals(dummy.getLog(), [])
        mgr()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['d']"])

class TransactionIndexationManagerTest(unittest.TestCase):

    # These really test the beforeCommitHook

    def test_transaction(self):
        get_transaction().begin()
        mgr = get_indexation_manager()
        dummy = Dummy('dummy')
        mgr.push(dummy, idxs=['bar'])
        self.assertEquals(dummy.getLog(), [])
        get_transaction().commit()
        self.assertEquals(dummy.getLog(), ["idxs dummy ['bar']"])

    def test_transaction_aborting(self):
        get_transaction().begin()
        mgr = get_indexation_manager()
        dummy = Dummy('dummy')
        mgr.push(dummy, idxs=['bar'])
        self.assertEquals(dummy.getLog(), [])
        get_transaction().abort()
        self.assertEquals(dummy.getLog(), [])


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(IndexationManagerTest),
        unittest.makeSuite(TransactionIndexationManagerTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
