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

""" Patchs for ZODB
"""

from zLOG import LOG, DEBUG, INFO

#
# Patch Transaction to add a before commit hook
# It won't be neccesarly anymore with ZODB-3.3
# See Synchronizers and beforeCompletion() method of Transaction
#

from ZODB.Transaction import Transaction

from Interface.Verify import verifyObject, DoesNotImplement
from Products.CPSCore.interfaces import ITransactionCommitSubscriber

def registerBeforeCommitSubscriber(self, subscriber):
    """Register a new before commit subscriber
    """
    try:
        verifyObject(ITransactionCommitSubscriber, subscriber)
    except DoesNotImplement:
        LOG("registerBeforeCommitSubscriber()", INFO,
            "Cannot register %s : Check implementation" %repr(subscriber))
        raise
    if subscriber not in self._before_commit_subscribers:
        LOG("ZODB.Transaction.register()", DEBUG, repr(subscriber))
        self._before_commit_subscribers.append(subscriber)

def abort(self, subtransaction=0, freeme=1):
    if (not subtransaction and
        self._before_commit_subscribers):
        for subscriber in self._before_commit_subscribers:
            subscriber.abort(self)
        self._before_commit_subscribers = []
    self.orig_abort(subtransaction, freeme)

def commit(self, subtransaction=None):
    if (self._before_commit_subscribers and
        not subtransaction):
        for subscriber in self._before_commit_subscribers:
            subscriber.commit(self)
        self._before_commit_subscribers = []
    self.orig_commit(subtransaction)

LOG("Patch ZODB.Transaction add a before commit hook", DEBUG, "Added")

Transaction._before_commit_subscribers = []
Transaction.registerBeforeCommitSubscriber = registerBeforeCommitSubscriber

if not getattr(Transaction, 'orig_commit', False):
    Transaction.orig_commit = Transaction.commit
    Transaction.commit = commit

if not getattr(Transaction, 'orig_abort', False):
    Transaction.orig_abort = Transaction.abort
    Transaction.abort = abort





