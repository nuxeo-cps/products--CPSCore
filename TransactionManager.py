# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Anguenot <ja@nuxeo.com>
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
""" Transaction Manager for CPS

Transaction manager for CPS that will be responsible of the execution
of ZODB transaction hooks registred by CPS. It will deal with order of
execution and defines a trivial and senseful ordering policy using the
order of registration and an integer value speciying the order level
for each hook. As well, note the transaction manager is responsible of
the execution of the hooks. (not the ZODB transaction itself)
"""

import logging
import bisect

import transaction
import zope.interface

from Products.CPSCore.interfaces import IBaseManager
from Products.CPSCore.BaseManager import BaseManager

_CPS_BCH_TXN_ATTRIBUTE = '_cps_before_commit_hooks_manager'

class BeforeCommitSubscribersManager(BaseManager):
    """Holds hooks that will be executed at the end of the transaction.
    """

    zope.interface.implements(IBaseManager)

    def __init__(self, txn):
        """Initialize and register this manager with the transaction.
        """
        self._sync = self.DEFAULT_SYNC
        self._status = self.DEFAULT_STATUS

        # List of (order, index, hook, args, kws) tuples added by
        # addbeforeCommitHook().  `index` is used to resolve ties on equal
        # `order` values, preserving the order in which the hooks were
        # registered.  Each time we append a tuple to _before_commit,
        # the current value of _before_commit_index is used for the
        # index, and then the latter is incremented by 1.
        self._before_commit = []
        self._before_commit_index = 0
        txn.addBeforeCommitHook(self)

        self.log = logging.getLogger("CPSCore BeforeCommitSubscribersManager")

    def addSubscriber(self, hook, args=(), kws=None, order=0):
        """Register a subscriber to call before the transaction is committed.

        The specified hook function will be called after the transaction's
        commit method has been called, but before the commit process has been
        started.  The hook will be passed the specified positional (`args`)
        and keyword (`kws`) arguments.  `args` is a sequence of positional
        arguments to be passed, defaulting to an empty tuple (no positional
        arguments are passed).  `kws` is a dictionary of keyword argument
        names and values to be passed, or the default None (no keyword
        arguments are passed).

        Multiple hooks can be registered and will be called in the order they
        were registered (first registered, first called), except that
        hooks registered with different `order` arguments are invoked from
        smallest `order` value to largest.  `order` must be an integer,
        and defaults to 0.

        For instance, a hook registered with order=1 will be invoked after
        another hook registered with order=-1 and before another registered
        with order=2, regardless of which was registered first.  When two
        hooks are registered with the same order, the first one registered is
        called first.

        Hooks are called only for a top-level commit.  A subtransaction
        commit or savepoint creation does not call any hooks.  If the
        transaction is aborted, hooks are not called, and are discarded.
        Calling a hook "consumes" its registration too:  hook registrations
        do not persist across transactions.  If it's desired to call the same
        hook on every transaction commit, then addBeforeCommitHook() must be
        called with that hook during every transaction; in such a case
        consider registering a synchronizer object via a TransactionManager's
        registerSynch() method instead.
        """

        # When the manager is disabled it won't add new hooks. It
        # means, it can be deactiveted for a while, thus won't add any
        # new one, and then be activated again and start adding some
        # again.
        if not self._status:
            self.log.debug("won't register %s with %s and %s with order %s"
                         %(repr(hook), args, kws, str(order)))
            return

        if not isinstance(order, int):
            raise ValueError("An integer value is required "
                             "for the order argument")
        if kws is None:
            kws = {}

        if self.isSynchronous():
            self.log.debug("executs %s with %s and %s" %
                           (repr(hook), args, kws))
            hook(*args, **kws)
            return

        self.log.debug("register %s with %s and %s with order %s"
                       %(repr(hook), args, kws, str(order)))
        bisect.insort(self._before_commit, (order, self._before_commit_index,
                                            hook, tuple(args), kws))
        self._before_commit_index += 1

    def __call__(self):
        """Execute the registred hooks

        This method is called by the transaction. Note, the registred
        hooks are executed by the TransactionManager itself and not by
        the transaction.
        """
        self.log.debug("__call__")

        while self._before_commit:
            order, index, hook, args, kws = self._before_commit.pop(0)
            self.log.debug("executs %s with %s and %s" %
                           (repr(hook), args, kws))
            hook(*args, **kws)
        self._before_commit_index = 0

        self.log.debug("__call__ done")

def del_before_commits_subscribers_manager():
    txn = transaction.get()
    setattr(txn, _CPS_BCH_TXN_ATTRIBUTE, None)

def get_before_commit_subscribers_manager():
    """Get the before commit subscribers manager.

    Creates it if needed.
    """
    txn = transaction.get()
    mgr = getattr(txn, _CPS_BCH_TXN_ATTRIBUTE, None)
    if mgr is None:
        mgr = BeforeCommitSubscribersManager(txn)
        setattr(txn, _CPS_BCH_TXN_ATTRIBUTE, mgr)
    return mgr
