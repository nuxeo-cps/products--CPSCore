# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Anguenot <ja@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
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
"""Manager for indexations that can be delayed until commit time.

Asynchronous by default.
"""

import logging
import transaction
import zope.interface

from Acquisition import aq_base

from Products.CPSCore.interfaces import IBaseManager
from Products.CPSCore.BaseManager import BaseManager
from Products.CPSCore.TransactionManager import get_transaction_manager

_TXN_MGR_ATTRIBUTE = '_cps_idx_manager'

# We don't want any other hooks executed before this one right now.  It
# will have an order of -100
_TXN_MGR_ORDER = -100

logger = logging.getLogger("CPSCore.IndexationManager")

class IndexationManager(BaseManager):
    """Holds data about reindexings to be done."""

    zope.interface.implements(IBaseManager)

    def __init__(self, mgr):
        """Initialize and register this manager with the transaction."""
        BaseManager.__init__(self, mgr, order=_TXN_MGR_ORDER)
        self._queue = []
        self._infos = {}

    def push(self, ob, idxs=None, with_security=False):
        """Add / update an object to reindex to the reindexing queue.

        Copes with security reindexation as well.
        """

        # Do not push anything if the subscriber is not enabled
        # When the manager is disabled it won't queue anything. It means, it
        # can be deactiveted for a while, thus won't queue, and then be
        # activated again and start queuing again.
        if not self._status:
            logger.debug("index object %r won't be processed" % ob)
            return

        if self.isSynchronous():
            logger.debug("index object %r" % ob)
            self.process(ob, idxs, with_security)
            return

        logger.debug("queue object %r idxs=%s secu=%s"
                     % (ob, idxs, with_security))

        # Compute a key for ob. id() is not enough when cut and paste
        # <id_of_ob, rpath>
        rpath = '/'.join(ob.getPhysicalPath())[1:]
        i = (id(aq_base(ob)), rpath) # XXX should use security manager too
        info = self._infos.get(i)
        if info is None:
            info = {
                'id': i,
                'object': ob,
                'idxs': idxs,
                'secu': with_security,
                }
            self._queue.append(info)
            self._infos[i] = info
        else:
            # Update idxs
            if idxs is not None:
                if idxs == []:
                    # Reindex everything
                    info['idxs'] = []
                else:
                    # Add indexes to previous
                    previous = info.setdefault('idxs', [])
                    if previous is None:
                        info['idxs'] = idxs
                    elif previous != []:
                        for idx in idxs:
                            if idx not in previous:
                                previous.append(idx)

            # Update secu
            info['secu'] = info['secu'] or with_security

        logger.debug("info %r" % info)

    def __call__(self):
        """Called when transaction commits.

        Does the actual indexing work.
        """

        # At this point, we start processing the queue. If any further
        # indexing happen during this, it still has to be treated.

        # Currently the data structures are such that this is not needed
        # (see unit tests).
        #_remove_indexation_manager()

        logger.debug("__call__")

        while self._queue:
            info = self._queue.pop(0)
            del self._infos[info['id']]

            logger.debug("__call__ processing %r" % info)
            self.process(info['object'], info['idxs'], info['secu'])

        logger.debug("__call__ done")

    def process(self, ob, idxs, secu):
        """Process an object, to reindex it."""
        # The object may have been removed from its container since,
        # even if the value we have is still wrapped.
        # Re-acquire it from the root
        # FIXME: do better, by treating also indexObject/unindexObject
        root = ob.getPhysicalRoot()
        path = ob.getPhysicalPath()
        old_ob = ob
        ob = root.unrestrictedTraverse(path, None)
        if ob is None:
            logger.debug("Object %r disappeared" % old_ob)
            return
        if idxs is not None:
            logger.debug("reindexObject %r idxs=%r" % (ob, idxs))
            ob._reindexObject(idxs=idxs)
        if secu:
            skip_self = (idxs == [] or
                         (idxs and 'allowedRolesAndUsers' in idxs))
            logger.debug("reindexObjectSecurity %r skip=%s" % (ob, skip_self))
            ob._reindexObjectSecurity(skip_self=skip_self)

def del_indexation_manager():
    txn = transaction.get()
    setattr(txn, _TXN_MGR_ATTRIBUTE, None)

def get_indexation_manager():
    """Get the indexation manager.

    Creates it if needed.
    """
    txn = transaction.get()
    mgr = getattr(txn, _TXN_MGR_ATTRIBUTE, None)
    if mgr is None:
        mgr = IndexationManager(get_transaction_manager())
        setattr(txn, _TXN_MGR_ATTRIBUTE, mgr)
    return mgr
