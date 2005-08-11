# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author : Julien Anguenot <ja@nuxeo.com>
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
"""This file contains all patches related to ZODB.

This work is currently within a branch over there :
http://svn.zope.org/ZODB/branches/anguenot-ordering-beforecommitsubscribers/

It should be available within ZODB-3.5 and thus be moved to CPSCompat
after this.

As well, see CPSCompat.PatchZODBTransaction
"""

from zLOG import LOG, DEBUG, INFO, DEBUG

import bisect

try:
    from ZODB.Transaction import Transaction
except ImportError, e:
    if str(e) != 'No module named Transaction': raise
    from transaction import Transaction

if not getattr(Transaction, '_old__init__', False):
    Transaction._old__init__ = Transaction.__init__
    def __init__(self, synchronizers=None, manager=None):
        self._old__init__(synchronizers, manager)
        self._before_commit_index = 0
    Transaction.__init__ = __init__

def getBeforeCommitHooks(self):
    # Don't return the hook order and index values because of
    # backward compatibility. As well, those are internals
    return iter([x[2:5] for x in self._before_commit])
Transaction.getBeforeCommitHooks = getBeforeCommitHooks

def addBeforeCommitHook(self, hook, args=(), kws=None, order=0):
    if not isinstance(order, int):
        raise ValueError("An integer value is required "
                         "for the order argument")
    if kws is None:
        kws = {}
    # `index` goes up by 1 on each append.  Then no two tuples can
    # compare equal, and indeed no more than the `order` and
    # `index` fields ever get compared when the tuples are compared
    # (because no two `index` fields are equal).
    bisect.insort(self._before_commit, (order, self._before_commit_index,
                                        hook, tuple(args), kws))
    self._before_commit_index += 1
Transaction.addBeforeCommitHook = addBeforeCommitHook

def beforeCommitHook(self, hook, *args, **kws):
    # Default order is zero (0)
    self.addBeforeCommitHook(hook, args, kws, order=0)
Transaction.beforeCommitHook = beforeCommitHook

def _callBeforeCommitHooks(self):
    # Call all hooks registered, allowing further registrations
    # during processing.
    while self._before_commit:
        order, index, hook, args, kws = self._before_commit.pop(0)
        hook(*args, **kws)
    self._before_commit_index = 0
Transaction._callBeforeCommitHooks = _callBeforeCommitHooks

LOG('PatchZODB.transaction', INFO,
    'CPSCore patch for before commit hook ordering')
