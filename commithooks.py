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
""" Commit hooks managers for CPS

Managers for CPS that will be responsible of the execution
of ZODB transaction hooks registred by CPS. It will deal with order of
execution and defines a trivial and sensible ordering policy using the
order of registration and an integer value speciying the order level
for each hook. As well, note the transaction manager is responsible of
the execution of the hooks. (not the ZODB transaction itself)

This module defines two managers :

 - BeforeCommitSubsribersManager
 - AfterCommitSubscribersManager

It defines as well two base classes that can be used to define new
subcscribers :

 - BeforeCommitHookSubscriber
 - AfterCommitHookSubscriber

"""

import logging
import bisect

import transaction
import zope.interface

from Products.CPSCore.interfaces import ICommitSubscriber
from Products.CPSCore.interfaces import IBeforeCommitSubscriber
from Products.CPSCore.interfaces import IAfterCommitSubscriber
from Products.CPSCore.interfaces import IZODBBeforeCommitHook
from Products.CPSCore.interfaces import IZODBAfterCommitHook

_CPS_BCH_TXN_ATTRIBUTE = '_cps_before_commit_hooks_manager'
_CPS_ACH_TXN_ATTRIBUTE = '_cps_after_commit_hooks_manager'

#
# Commit subsriber definitions
#

class CommitSubscriber(object):
    """Base commit subscriber definition
    """
    zope.interface.implements(ICommitSubscriber)

    # Not synchronous by default
    # XXX This may be monkey-patched by unit-tests.
    DEFAULT_SYNC = False

    # Enabled by default
    DEFAULT_STATUS = True

    def __init__(self, mgr, order=0):
        self._sync = self.DEFAULT_SYNC
        self._status = self.DEFAULT_STATUS
        mgr.addSubscriber(self, order=order)

    def setSynchronous(self, sync):
        if sync:
            self()
        self._sync = sync

    def isSynchronous(self):
        return self._sync

    def __call__(self):
        raise NotImplementedError

    def push(self, *args):
        raise NotImplementedError

    def enable(self):
        self._status = True

    def disable(self):
        self._status = False

class BeforeCommitSubscriber(CommitSubscriber):
    """Before commit subscriber definition
    """
    zope.interface.implements(IBeforeCommitSubscriber)

class AfterCommitSubscriber(BeforeCommitSubscriber):
    """After commit subscriber definition
    """
    zope.interface.implements(IAfterCommitSubscriber)

    def __call__(self, status=True):
        raise NotImplementedError

#
# Commit subscriber manager definitions
#

class BeforeCommitSubscribersManager(BeforeCommitSubscriber):
    """Holds subscribers that will be executed at the end of the transaction.
    """

    zope.interface.implements(IBeforeCommitSubscriber, IZODBBeforeCommitHook)

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

        self.log = logging.getLogger(
            "CPSCore.commithooks.BeforeCommitSubscribersManager")

    def addSubscriber(self, subscriber, args=(), kws=None, order=0):
        """Register a subscriber to call before the transaction is committed.

        The specified subscriber function will be called after the
        transaction's commit method has been called, but before the
        commit process has been started.  The subscriber will be
        passed the specified positional (`args`) and keyword (`kws`)
        arguments.  `args` is a sequence of positional arguments to be
        passed, defaulting to an empty tuple (no positional arguments
        are passed).  `kws` is a dictionary of keyword argument names
        and values to be passed, or the default None (no keyword
        arguments are passed).

        Multiple subscribers can be registered and will be called in
        the order they were registered (first registered, first
        called), except that subscribers registered with different
        `order` arguments are invoked from smallest `order` value to
        largest.  `order` must be an integer, and defaults to 0.

        For instance, a subscriber registered with order=1 will be
        invoked after another subscriber registered with order=-1 and
        before another registered with order=2, regardless of which
        was registered first.  When two subscribers are registered
        with the same order, the first one registered is called first.

        Subscribers are called only for a top-level commit.  A
        subtransaction commit or savepoint creation does not call any
        subscribers.  If the transaction is aborted, subscribers are
        not called, and are discarded.

        Calling a subscriber"consumes" its registration too: subscriber
        registrations do not persist across
        transactions.  If it's desired to call the same subscriber on
        every transaction commit, then addSubscriber()
        must be called with that subscriber during every transaction;
        in such a case consider registering a synchronizer object via
        a TransactionManager's registerSynch() method instead.
        """

        # When the manager is disabled it won't add new subscribers. It
        # means, it can be deactiveted for a while, thus won't add any
        # new one, and then be activated again and start adding some
        # again.
        if not self._status:
            self.log.debug("won't register %s with %s and %s with order %s"
                         %(repr(subscriber), args, kws, str(order)))
            return

        if not isinstance(order, int):
            raise ValueError("An integer value is required "
                             "for the order argument")
        if kws is None:
            kws = {}

        if self.isSynchronous():
            self.log.debug("executs %s with %s and %s" %
                           (repr(subscriber), args, kws))
            subscriber(*args, **kws)
            return

        self.log.debug("register %s with %s and %s with order %s"
                       %(repr(subscriber), args, kws, str(order)))
        bisect.insort(self._before_commit, (order, self._before_commit_index,
                                            subscriber, tuple(args), kws))
        self._before_commit_index += 1

    def __call__(self):

        """Execute the registred subscribers

        This method is called by the transaction. Note, the registred
        subscribers are executed by the the
        BeforeCommitSubscribersManager itself and not by the
        transaction.
        """
        self.log.debug("__call__")

        while self._before_commit:
            order, index, subscriber, args, kws = self._before_commit.pop(0)
            self.log.debug("executs %s with %s and %s" %
                           (repr(subscriber), args, kws))
            subscriber(*args, **kws)
        self._before_commit_index = 0

        self.log.debug("__call__ done")

class AfterCommitSubscribersManager(AfterCommitSubscriber):
    """Holds subscribers that will be executed after the
    """

    zope.interface.implements(IAfterCommitSubscriber, IZODBAfterCommitHook)

    def __init__(self, txn):
        """Initialize and register this manager with the transaction.
        """
        self._sync = self.DEFAULT_SYNC
        self._status = self.DEFAULT_STATUS

        # List of (order, index, hook, args, kws) tuples added by
        # addAfterCommitHook().  `index` is used to resolve ties on equal
        # `order` values, preserving the order in which the hooks were
        # registered.  Each time we append a tuple to _before_commit,
        # the current value of _before_commit_index is used for the
        # index, and then the latter is incremented by 1.
        self._after_commit = []
        self._after_commit_index = 0
        txn.addAfterCommitHook(self)

        self.log = logging.getLogger(
            "CPSCore.commithooks.AfterCommitSubscribersManager")

    def addSubscriber(self, subscriber, args=(), kws=None, order=0):
        """Register a subscriber to call after a transaction commit attempt.

         The specified subscriber function will be called after the
         transaction commit succeeds or aborts.  The first argument
         passed to the subscriber is a Boolean value, true if the
         commit succeeded, or false if the commit aborted.  `args`
         specifies additional positional, and `kws` keyword, arguments
         to pass to the subscriber.  `args` is a sequence of
         positional arguments to be passed, defaulting to an empty
         tuple (only the true/false success argument is passed).
         `kws` is a dictionary of keyword argument names and values to
         be passed, or the default None (no keyword arguments are
         passed).

         Multiple subscribers can be registered and will be called in
         the order they were registered (first registered, first
         called). except that hooks registered with different `order`
         arguments are invoked from smallest `order` value to largest.
         `order` must be an integer, and defaults to 0.

         For instance, a hook registered with order=1 will be invoked
         after another hook registered with order=-1 and before
         another registered with order=2, regardless of which was
         registered first.  When two hooks are registered with the
         same order, the first one registered is called first.

         This method can also be called from a subscriber:
         an executing subscriber can register more subscribers.
         Applications should take care to avoid creating infinite
         loops by recursively registering subscribers.

         Subscribers are called only for a top-level commit.  A
         subtransaction commit or savepoint creation does not call any
         subscribers.  Calling a subscriber"consumes" its registration:
         subscriber registrations do not persist across transactions.

         If it's desired to call the same subscriber on every
         transaction commit, then addSubscriber() must be called with
         that subscriber during every transaction; in such a case
         consider registering a synchronizer object via a
         TransactionManager's registerSynch() method instead.
         """

        # When the manager is disabled it won't add new subscribers. It
        # means, it can be deactiveted for a while, thus won't add any
        # new one, and then be activated again and start adding some
        # again.
        if not self._status:
            self.log.debug("won't register %s with %s and %s with order %s"
                         %(repr(subscriber), args, kws, str(order)))
            return

        if not isinstance(order, int):
            raise ValueError("An integer value is required "
                             "for the order argument")
        if kws is None:
            kws = {}

        if self.isSynchronous():
            self.log.debug("executs %s with %s and %s" %
                           (repr(subscriber), args, kws))
            # False for the fact the the transaction hasn't been commited
            subscriber(False, *args, **kws)
            return

        self.log.debug("register %s with %s and %s with order %s"
                       %(repr(subscriber), args, kws, str(order)))
        bisect.insort(self._after_commit, (order, self._after_commit_index,
                                           subscriber, tuple(args), kws))
        self._after_commit_index += 1

    def __call__(self, status=True):
        """Execute the registred subscribers

        This method is called by the transaction. Note, the registred
        subscribers are executed by the
        AfterCommitSubscribersManager itself and not by the
        transaction.

        status is the status of the
        """
        self.log.debug("__call__")

        while self._after_commit:
            order, index, subscriber, args, kws = self._after_commit.pop(0)
            self.log.debug("executs %s with %s and %s" %
                           (repr(subscriber), args, kws))
            subscriber(status, *args, **kws)
        self._after_commit_index = 0

        self.log.debug("__call__ done")

#
# CPS Helpers
#

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

def del_after_commits_subscribers_manager():
    txn = transaction.get()
    setattr(txn, _CPS_ACH_TXN_ATTRIBUTE, None)

def get_after_commit_subscribers_manager():
    """Get the after commit subscribers manager.

    Creates it if needed.
    """
    txn = transaction.get()
    mgr = getattr(txn, _CPS_ACH_TXN_ATTRIBUTE, None)
    if mgr is None:
        mgr = AfterCommitSubscribersManager(txn)
        setattr(txn, _CPS_ACH_TXN_ATTRIBUTE, mgr)
    return mgr
