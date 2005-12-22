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
"""After commit subscribers manager tests
"""

import unittest
import transaction

from Testing import ZopeTestCase
from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem

from Products.CPSCore.interfaces import IAfterCommitSubscriber
from Products.CPSCore.commithooks import _CPS_ACH_TXN_ATTRIBUTE
from Products.CPSCore.commithooks import AfterCommitSubscribersManager
from Products.CPSCore.commithooks import get_after_commit_subscribers_manager
from Products.CPSCore.commithooks import get_before_commit_subscribers_manager
from Products.CPSCore.commithooks import del_after_commits_subscribers_manager

class FakeTransaction:
    def addAfterCommitHook(self, hook):
        pass

log = []
def reset_log():
    del log[:]

def hook(status=True, arg='no_arg', kw1='no_kw1', kw2='no_kw2'):
    log.append("status %s arg %r kw1 %r kw2 %r" % (status, arg, kw1, kw2))

class AfterCommitSubscribersManagerTest(unittest.TestCase):

    def test_interfaces(self):
        from zope.interface.verify import verifyClass
        verifyClass(IAfterCommitSubscriber, AfterCommitSubscribersManager)

    def test_fixtures(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr._after_commit, [])
        self.assertEqual(mgr._after_commit_index, 0)
        self.assertEqual(mgr._sync, False)
        self.assertEqual(mgr.isSynchronous(), False)
        self.assertEqual(mgr.isSynchronous(), mgr._sync)
        self.assertEqual(mgr._status, True)

    def test_status_api(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr._status, True)
        mgr.disable()
        self.assertEqual(mgr._status, False)
        mgr.enable()
        self.assertEqual(mgr._status, True)

    def test_async(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())
        mgr.addSubscriber(hook, '1')

        self.assertEqual(log, [])
        mgr()
        self.assertEqual(log,
                         ["status True arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_sync(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())
        mgr.setSynchronous(True)
        mgr.addSubscriber(hook, '1')

        self.assertEqual(log,
                         ["status False arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_status_as_async(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr._status, True)
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
            ["status True arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_status_as_sync(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())

        self.assertEqual(mgr._status, True)
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
            ["status False arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "status False arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "status False arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "status False arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_hooks_registration_without_order(self):

        mgr = AfterCommitSubscribersManager(FakeTransaction())

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
            ["status True arg '1' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '2' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '3' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '5' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '7' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

    def test_hooks_registration_with_order(self):

        # Here, we test the ordering policy.
        # order of registration + order parameter

        mgr = AfterCommitSubscribersManager(FakeTransaction())

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
            ["status True arg '2' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '6' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '1' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '4' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '7' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '3' kw1 'no_kw1' kw2 'no_kw2'",
             "status True arg '5' kw1 'no_kw1' kw2 'no_kw2'"],
            log)

        reset_log()

class AfterCommitSubscribersManagerIntegrationTest(unittest.TestCase):

    # These really test the beforeCommitHook on a real transaction

    def test_transaction_mecanism(self):
        transaction.begin()
        mgr = get_after_commit_subscribers_manager()
        transaction.commit()
        self.assertEqual(log, [])

    def test_transaction_with_a_hook(self):
        transaction.begin()
        mgr = get_after_commit_subscribers_manager()
        mgr.addSubscriber(hook, '1')
        transaction.commit()
        self.assertEqual(
            log, ["status True arg '1' kw1 'no_kw1' kw2 'no_kw2'"])
        reset_log()

    def test_transaction_aborting(self):
        transaction.begin()
        mgr = get_after_commit_subscribers_manager()
        mgr.addSubscriber(hook, '1')
        transaction.abort()
        self.assertEqual(log, [])

    def test_get_del_after_commits_subscribers_manager(self):
        _marker = 'marker'

        # No transaction manager registred over there
        self.assertEqual(
            getattr(transaction.get(),
                    _CPS_ACH_TXN_ATTRIBUTE, _marker), _marker)

        # This will check and add one
        get_after_commit_subscribers_manager()
        self.assert_(
            getattr(transaction.get(), _CPS_ACH_TXN_ATTRIBUTE, None))

        # This will remove it
        del_after_commits_subscribers_manager()
        self.assertEqual(
            getattr(transaction.get(), _CPS_ACH_TXN_ATTRIBUTE, _marker), None)

class AfterCommitSubscribersManagerAdvancedTest(ZopeTestCase.PortalTestCase):

    def _setup(self):
        self._setupUserFolder()
        self._setupUser()
        self.login()

    def getPortal(self):
        self.app.portal = Folder('portal')
        return self.app.portal

    def test_persistency(self):

        def subscriber(status, portal):
            # Subscriber trying to change a persitent object
            item = getattr(portal, 'item')
            item.title = 'changed'

        transaction.begin()

        portal = self.getPortal()
        portal._setObject('item', SimpleItem('item'))
        item = getattr(portal, 'item')
        item.title = 'title'

        # Register the subscriber
        mgr = get_after_commit_subscribers_manager()
        mgr.addSubscriber(subscriber, args=(portal,))

        self.assertEqual(item.title, 'title')

        transaction.commit()

        # It doesn't change the title
        self.assertEqual(item.title, 'title')

    def test_commit_fails(self):

        def bcsubscriber():
            raise Exception

        transaction.begin()
        # Register the subscribers
        get_before_commit_subscribers_manager().addSubscriber(bcsubscriber)
        get_after_commit_subscribers_manager().addSubscriber(hook)

        self.assertRaises(Exception, transaction.commit)
        # This is not an internal commit error
        self.assertEqual(log, [])

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(AfterCommitSubscribersManagerTest),
        unittest.makeSuite(AfterCommitSubscribersManagerIntegrationTest),
        unittest.makeSuite(AfterCommitSubscribersManagerAdvancedTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
