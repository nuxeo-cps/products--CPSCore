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

from zLOG import LOG, DEBUG
from Acquisition import aq_base

try:
    import transaction
except ImportError:
    # BBB: for Zope 2.7
    from Products.CMFCore.utils import transaction
    # The following is missing from CMF 1.5.2
    def BBBget():
        return get_transaction()
    transaction.get = BBBget

from Products.CPSCore.TransactionManager import get_transaction_manager

_TXN_MGR_ATTRIBUTE = '_cps_idx_manager'

# We don't want any other hooks executed before this one right now.  It
# will have an order of -100
_TXN_MGR_ORDER = -100

class IndexationManager:
    """Holds data about reindexings to be done."""

    # Not synchronous by default
    # XXX This may be monkey-patched by unit-tests.
    DEFAULT_SYNC = False

    def __init__(self, mgr):
        """Initialize and register this manager with the transaction."""
        self._queue = []
        self._infos = {}
        self._sync = self.DEFAULT_SYNC
        mgr.addBeforeCommitHook(self, order=_TXN_MGR_ORDER)

    def setSynchonous(self, sync):
        """Set queuing mode."""
        if sync:
            self()
        self._sync = sync

    def isSynchonous(self):
        """Get queuing mode."""
        return self._sync

    def push(self, ob, idxs=None, with_security=False):
        """Add / update an object to reindex to the reindexing queue.

        Copes with security reindexation as well.
        """
        if self.isSynchonous():
            LOG("IndexationManager", DEBUG, "index object %r" % ob)
            self.process(ob, idxs, with_security)
            return

        LOG("IndexationManager", DEBUG, "queue object %r idxs=%s secu=%s"
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

        LOG("IndexationManager", DEBUG, "info %r" % info)

    def __call__(self):
        """Called when transaction commits.

        Does the actual indexing work.
        """

        # At this point, we start processing the queue. If any further
        # indexing happen during this, it still has to be treated.

        # Currently the data structures are such that this is not needed
        # (see unit tests).
        #_remove_indexation_manager()

        LOG("IndexationManager", DEBUG, "__call__")

        while self._queue:
            info = self._queue.pop(0)
            del self._infos[info['id']]

            LOG("IndexationManager", DEBUG, "__call__ processing %r" % info)
            self.process(info['object'], info['idxs'], info['secu'])

        LOG("IndexationManager", DEBUG, "__call__ done")

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
            LOG("IndexationManager", DEBUG, "Object %r disappeared" % old_ob)
            return
        if idxs is not None:
            LOG("IndexationManager", DEBUG, "reindexObject %r idxs=%r"
                % (ob, idxs))
            ob._reindexObject(idxs=idxs)
        if secu:
            skip_self = (idxs == [] or
                         (idxs and 'allowedRolesAndUsers' in idxs))
            LOG("IndexationManager", DEBUG,
                "reindexObjectSecurity %r skip=%s" % (ob, skip_self))
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
