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
"""Transaction Manager tests
"""

import unittest

import transaction

from Products.CPSCore.interfaces import IBeforeCommitSubscriber
from Products.CPSCore.commithooks import _CPS_BCH_TXN_ATTRIBUTE
from Products.CPSCore.commithooks import BeforeCommitSubscribersManager
from Products.CPSCore.commithooks import get_before_commit_subscribers_manager
from Products.CPSCore.commithooks import del_before_commits_subscribers_manager

class FakeTransaction:
    def addBeforeCommitHook(self, hook):
        pass

log = []
def reset_log():
    del log[:]

def hook(arg='no_arg', kw1='no_kw1', kw2='no_kw2'):
    log.append("arg %r kw1 %r kw2 %r" % (arg, kw1, kw2))

class BeforeCommitSubscribersManagerTest(unittest.TestCase):

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        verifyClass(IBeforeCommitSubscriber, BeforeCommitSubscribersManager)

    def test_fixtures(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr._before_commit, [])
        self.assertEqual(mgr._before_commit_index, 0)
        self.assertEqual(mgr._sync, False)
        self.assertEqual(mgr.isSynchronous(), False)
        self.assertEqual(mgr.isSynchronous(), mgr._sync)
        self.assertEqual(mgr.enabled, True)

    def test_status_api(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr.enabled, True)
        mgr.disable()
        self.assertEqual(mgr.enabled, False)
        mgr.enable()
        self.assertEqual(mgr.enabled, True)

    def test_async(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())
        mgr.addSubscriber(hook, '1')

        self.assertEqual(log, [])
        mgr()
        self.assertEqual(log, ["arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_sync(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())
        mgr.setSynchronous(True)
        mgr.addSubscriber(hook, '1')

        self.assertEqual(log, ["arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_status_as_async(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr.enabled, True)
        self.assertEqual(mgr._sync, False)

        # Disable subscriber
        mgr.disable()

        # Register hooks
        mgr.addSubscriber(hook, '1')
        mgr.addSubscriber(hook, '2')
        mgr.addSubscriber(hook, '3')

        # Enable subscriber
        mgr.enable()
        
        mgr.addSubscriber(hook, '4')
        mgr.addSubscriber(hook, '5')
        mgr.addSubscriber(hook, '6')
        mgr.addSubscriber(hook, '7')

        # Execute
        mgr()
        
        # Nothing has been executed since it's disabled
        self.assertEqual(
            ["arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_status_as_sync(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr.enabled, True)
        self.assertEqual(mgr._sync, False)

        # Sync = True
        mgr.setSynchronous(True)

        # Disable subscriber
        mgr.disable()

        # Register hooks
        mgr.addSubscriber(hook, '1')
        mgr.addSubscriber(hook, '2')
        mgr.addSubscriber(hook, '3')

        # Enable subscriber
        mgr.enable()
        
        mgr.addSubscriber(hook, '4')
        mgr.addSubscriber(hook, '5')
        mgr.addSubscriber(hook, '6')
        mgr.addSubscriber(hook, '7')

        # Nothing has been executed since it's disabled
        self.assertEqual(
            ["arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_hooks_registration_without_order(self):

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        # Register hooks
        mgr.addSubscriber(hook, '1')
        mgr.addSubscriber(hook, '2')
        mgr.addSubscriber(hook, '3')
        mgr.addSubscriber(hook, '4')
        mgr.addSubscriber(hook, '5')
        mgr.addSubscriber(hook, '6')
        mgr.addSubscriber(hook, '7')

        # Execute
        mgr()

        # The hooks are executed in the order of execution
        self.assertEqual(
            ["arg '1' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '2' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '3' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_hooks_registration_with_order(self):

        # Here, we test the ordering policy.
        # order of registration + order parameter

        mgr = BeforeCommitSubscribersManager(FakeTransaction())

        # Register hooks
        mgr.addSubscriber(hook, '1', order=0)
        mgr.addSubscriber(hook, '2', order=-999999)
        mgr.addSubscriber(hook, '3', order=999999)
        mgr.addSubscriber(hook, '4', order=0)
        mgr.addSubscriber(hook, '5', order=999999)
        mgr.addSubscriber(hook, '6', order=-999999)
        mgr.addSubscriber(hook, '7', order=0)

        # Execute
        mgr()

        # The hooks are executed in the order of execution
        self.assertEqual(
            ["arg '2' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '1' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '7' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '3' kw1 'no_kw1' kw2 'no_kw2'",
             "arg '5' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

class BeforeCommitSubscribersManagerIntegrationTest(unittest.TestCase):

    # These really test the beforeCommitHook on a real transaction

    def test_transaction_mecanism(self):
        transaction.begin()
        mgr = get_before_commit_subscribers_manager()
        transaction.commit()
        self.assertEqual(log, [])

    def test_transaction_with_a_hook(self):
        transaction.begin()
        mgr = get_before_commit_subscribers_manager()
        mgr.addSubscriber(hook, '1')
        transaction.commit()
        self.assertEqual(
            log, ["arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_before_commit_subscribers_manager()
        mgr.addSubscriber(hook, '1')
        transaction.abort()
        self.assertEqual(log, [])

    def test_get_del_before_commits_subscribers_manager(self):
        _marker = 'marker'

        # No transaction manager registred over there
        self.assertEqual(
            getattr(transaction.get(),
                    _CPS_BCH_TXN_ATTRIBUTE, _marker), _marker)

        # This will check and add one
        get_before_commit_subscribers_manager()
        self.assert_(
            getattr(transaction.get(), _CPS_BCH_TXN_ATTRIBUTE, None))

        # This will remove it
        del_before_commits_subscribers_manager()
        self.assertEqual(
            getattr(transaction.get(), _CPS_BCH_TXN_ATTRIBUTE, _marker), None)

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(BeforeCommitSubscribersManagerTest),
        unittest.makeSuite(BeforeCommitSubscribersManagerIntegrationTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
