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

# Extends ZODB Transaction to support before commit subscribers
import PatchZODB

from Products.CPSCore.interfaces import ITransactionCommitSubscriber

class BaseTCSubscriber:
    """Base transaction subscriber class
    """

    __implements__ = (
        ITransactionCommitSubscriber,
        )

    def __init__(self):
        self._queue = []
        self._transaction_done = True

    def register(self):
        get_transaction().registerBeforeCommitSubscriber(self)
        self._transaction_done = False

    def commit(self, transaction):
        raise NotImplementedError

    def abort(self, transaction):
        self._queue = []
        self._transaction_done = True

    def push(self, ob, **kw):
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

    def _getObjectsInQueue(self):
        return [x['object'] for x in self._queue]

    def commit(self, transaction):
        for struct in self._queue:
            if struct['with_security']:
                try:
                    reindex_self = 1
                    if struct['reindex']:
                        reindex_self = 0
                    struct['object']._reindexObjectSecurity(reindex_self)
                except AttributeError:
                    pass
            if struct['reindex']:
                try:
                    struct['object']._reindexObject(idxs=struct['idxs'])
                except AttributeError:
                    pass
        self._queue = []
        self._transaction_done = True

    def push(self, ob, idxs=[], with_security=0, **kw):
        """Add / update an object to reindex within the queue

        Cope with security reindexation as well.
        """

        _objects = self._getObjectsInQueue()

        if ob not in _objects:

            struct = {
                'object':ob,
                'idxs' : idxs,
                'with_security':with_security,
                }

            if not with_security:
                struct['reindex'] = 1
            else:
                struct['reindex'] = 0

            self._queue.append(struct)
        else:
            struct = self._queue[_objects.index(ob)]

            if idxs:
                struct['reindex'] = 1
            for idx in idxs:
                if idx not in struct['idxs']:
                    struct['idxs'].append(idx)

            if with_security and not struct['with_security']:
                struct['with_security'] = 1
                struct['idxs'].append('allowedRolesAndUsers')

            #self._queue.append(old_struct)


###################################################
# Register Subscribers
###################################################

IndexationManager = IndexationManagerTCSubscriber()
IndexationManager.register()
