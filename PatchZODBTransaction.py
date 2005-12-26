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

"""Patch ZODB transaction for after commit hooks as implemented there

http://svn.zope.org/ZODB/branches/anguenot-after_commit_hooks/

This should be merged within ZODB trunk (3.7.x) version and thus this
patch will have to move within CPSCompat
"""

import logging
import thread
import sys
import warnings
import weakref
import traceback
from cStringIO import StringIO

from transaction import Transaction
from transaction._transaction import Status
from transaction._transaction import _marker
from transaction._transaction import Savepoint

from ZODB.loglevels import TRACE


if True:

    def getAfterCommitHooks(self):
        return iter(self._after_commit)
    Transaction.getAfterCommitHooks = getAfterCommitHooks

    def addAfterCommitHook(self, hook, args=(), kws=None):
        if kws is None:
            kws = {}
        self._after_commit.append((hook, tuple(args), kws))
    Transaction.addAfterCommitHook = addAfterCommitHook

    def _callAfterCommitHooks(self, status=True):
        # Avoid to abort anything at the end if no hooks are registred.
        if not self._after_commit:
            return
        # Call all hooks registered, allowing further registrations
        # during processing.  Note that calls to addAterCommitHook() may
        # add additional hooks while hooks are running, and iterating over a
        # growing list is well-defined in Python.
        for hook, args, kws in self._after_commit:
            # The first argument passed to the hook is a Boolean value,
            # true if the commit succeeded, or false if the commit aborted.
            try:
                hook(status, *args, **kws)
            except:
                # We need to catch the exceptions if we want all hooks
                # to be called
                self.log.error("Error in after commit hook exec in %s ",
                               hook, exc_info=sys.exc_info())
        # The transaction is already committed. It must not have
        # further effects after the commit.
        for rm in self._resources:
            try:
                rm.abort(self)
            except:
                # XXX should we take further actions here ?
                self.log.error("Error in abort() on manager %s",
                               rm, exc_info=sys.exc_info())
        self._after_commit = []
        self._before_commit = []
    Transaction._callAfterCommitHooks = _callAfterCommitHooks

    def _saveAndGetCommitishError(self):
        self.status = Status.COMMITFAILED
        # Save the traceback for TransactionFailedError.
        ft = self._failure_traceback = StringIO()
        t, v, tb = sys.exc_info()
        # Record how we got into commit().
        traceback.print_stack(sys._getframe(1), None, ft)
        # Append the stack entries from here down to the exception.
        traceback.print_tb(tb, None, ft)
        # Append the exception type and value.
        ft.writelines(traceback.format_exception_only(t, v))
        return t, v, tb
    Transaction._saveAndGetCommitishError = _saveAndGetCommitishError

    def _saveAndRaiseCommitishError(self):
        t, v, tb = self._saveAndGetCommitishError()
        raise t, v, tb
    Transaction._saveAndRaiseCommitishError = _saveAndRaiseCommitishError

    def __init__(self, synchronizers=None, manager=None):
        self.status = Status.ACTIVE
        # List of resource managers, e.g. MultiObjectResourceAdapters.
        self._resources = []

        # Weak set of synchronizer objects to call.
        if synchronizers is None:
            from ZODB.utils import WeakSet
            synchronizers = WeakSet()
        self._synchronizers = synchronizers

        self._manager = manager

        # _adapters: Connection/_p_jar -> MultiObjectResourceAdapter[Sub]
        self._adapters = {}
        self._voted = {} # id(Connection) -> boolean, True if voted
        # _voted and other dictionaries use the id() of the resource
        # manager as a key, because we can't guess whether the actual
        # resource managers will be safe to use as dict keys.

        # The user, description, and _extension attributes are accessed
        # directly by storages, leading underscore notwithstanding.
        self._extension = {}

        self.log = logging.getLogger("txn.%d" % thread.get_ident())
        self.log.log(TRACE, "new transaction")

        # If a commit fails, the traceback is saved in _failure_traceback.
        # If another attempt is made to commit, TransactionFailedError is
        # raised, incorporating this traceback.
        self._failure_traceback = None

        # List of (hook, args, kws) tuples added by addBeforeCommitHook().
        self._before_commit = []

        # List of (hook, args, kws) tuples added by addAfterCommitHook().
        self._after_commit = []
    Transaction.__init__ = __init__

    def commit(self, subtransaction=_marker, deprecation_wng=True):
        if subtransaction is _marker:
            subtransaction = 0
        elif deprecation_wng:
            from ZODB.utils import deprecated37
            deprecated37("subtransactions are deprecated; instead of "
                         "transaction.commit(1), use "
                         "transaction.savepoint(optimistic=True) in "
                         "contexts where a subtransaction abort will never "
                         "occur, or sp=transaction.savepoint() if later "
                         "rollback is possible and then sp.rollback() "
                         "instead of transaction.abort(1)")

        if self._savepoint2index:
            self._invalidate_all_savepoints()

        if subtransaction:
            # TODO deprecate subtransactions
            self._subtransaction_savepoint = self.savepoint(optimistic=True)
            return

        if self.status is Status.COMMITFAILED:
            self._prior_operation_failed() # doesn't return

        self._callBeforeCommitHooks()

        self._synchronizers.map(lambda s: s.beforeCompletion(self))
        self.status = Status.COMMITTING

        try:
            self._commitResources()
            self.status = Status.COMMITTED
        except:
            t, v, tb = self._saveAndGetCommitishError()
            self._callAfterCommitHooks(status=False)
            raise t, v, tb
        else:
            if self._manager:
                self._manager.free(self)
            self._synchronizers.map(lambda s: s.afterCompletion(self))
            self._callAfterCommitHooks(status=True)
        self.log.log(TRACE, "commit")
    Transaction.commit = commit

    def savepoint(self, optimistic=False):
        if self.status is Status.COMMITFAILED:
            self._prior_operation_failed() # doesn't return, it raises

        try:
            savepoint = Savepoint(self, optimistic, *self._resources)
        except:
            self._cleanup(self._resources)
            self._saveAndRaiseCommitishError() # reraises!

        if self._savepoint2index is None:
            self._savepoint2index = weakref.WeakKeyDictionary()
        self._savepoint_index += 1
        self._savepoint2index[savepoint] = self._savepoint_index

        return savepoint
    Transaction.savepoint = savepoint

    def rollback(self):
        transaction = self.transaction
        if transaction is None:
            raise interfaces.InvalidSavepointRollbackError
        transaction._remove_and_invalidate_after(self)

        try:
            for savepoint in self._savepoints:
                savepoint.rollback()
        except:
            # Mark the transaction as failed.
            transaction._saveAndRaiseCommitishError() # reraises!
    Transaction.rollback = rollback

