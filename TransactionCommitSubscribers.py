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

"""Thid module contains ZODB before transaction commit subscribers

The Transaction extensions are defined within PatchZODB.
"""

from zLOG import LOG, DEBUG

from Interface.Verify import verifyObject, DoesNotImplement
from Products.CPSCore.interfaces import ITransactionCommitSubscriber

class TCSubscribersRegistry:
    """Pre-commit Transaction susbcribers registry
    """

    def __init__(self):
        self._before_commit_subscribers = []

    def register(self, subscriber):
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

    def getSubscribers(self):
        return self._before_commit_subscribers

class BaseTCSubscriber:
    """Base transaction subscriber class
    """

    __implements__ = (
        ITransactionCommitSubscriber,
        )

    def commit(self, transaction):
        raise NotImplementedError

    def abort(self, transaction):
        raise NotImplementedError

class IndexationManagerTCSubscriber(BaseTCSubscriber):
    """Indexation Manager Transition Commit Subscriber

    The goal in here it to provide single indexation at the end of a
    transaction for objects that have been modified several times
    during the same transaction
    """

    __implements__ = (
        ITransactionCommitSubscriber,
        )

    def __init__(self):
        self._queue = []
        self._transaction_done = True

    def _getObjectsInQueue(self):
        return [x['object'] for x in self._queue]

    def commit(self, transaction):
        ##LOG("IndexationManager.comit()" , DEBUG, "START")
        for struct in self._queue:
            LOG("Schedule for reindexation", DEBUG, str(struct))
            if struct['with_security'] and struct['reindex']:
                try:
                    struct['object']._reindexObjectSecurity(reindex_self=0)
                    struct['object']._reindexObject()
                except AttributeError:
                    pass
            elif (not struct['with_security']) and struct['reindex']:
                try:
                    struct['object']._reindexObject(idxs=struct['idxs'])
                except AttributeError:
                    pass
            elif struct['with_security'] and (not struct['reindex']):
                try:
                    struct['object']._reindexObjectSecurity(reindex_self=1)
                except AttributeError:
                    pass
        self._queue = []
        self._transaction_done = True

    def abort(self, transaction):
        self._queue = []
        self._transaction_done = True

    def push(self, ob, idxs=None, with_security=0, **kw):
        """Add / update an object to reindex within the queue

        Cope with security reindexation as well.
        """

        ##LOG("IndexationManager.push()" , DEBUG, repr(ob))

        _objects = self._getObjectsInQueue()

        if ob not in _objects:
            struct = {
                'object':ob,
                'idxs' : idxs,
                'with_security':with_security,
                }
            struct['reindex'] = idxs is not None and True or False
            ##LOG("Struct---------", DEBUG, str(struct))
            self._queue.append(struct)
        else:
            struct = self._queue[_objects.index(ob)]

            # if no former reindexation requested
            if not struct['reindex']:
                # Flag for reindexation if idxs
                struct['reindex'] = idxs is not None

            # Here, we reindex everything
            if idxs == []:
                struct['idxs'] = []

            # if idxs formerly given and some more added
            # if struct['idxs'] == [] then we are reindexing
            # everything thus it won't enter this loop
            elif struct['idxs'] and idxs is not None:
                for idx in idxs:
                    if idx not in struct['idxs']:
                        struct['idxs'].append(idx)

            # Flag security reindexation
            if with_security:
                struct['with_security'] = with_security

            ##LOG("Struct---------", DEBUG, str(struct))

###################################################
# Register Subscribers
###################################################

TCRegistry = TCSubscribersRegistry()

# Indexation Manager
IndexationManager = IndexationManagerTCSubscriber()

TCRegistry.register(IndexationManager)
