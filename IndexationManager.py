# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Anguenot <ja@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
#          Georges Racinet <georges@racinet.fr>
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

from Products.CMFCore.utils import getToolByName

from Products.CPSCore.interfaces import IBeforeCommitSubscriber
from Products.CPSCore.commithooks import BeforeCommitSubscriber
from Products.CPSCore.commithooks import get_before_commit_subscribers_manager

_TXN_MGR_ATTRIBUTE = '_cps_idx_manager'

ACTION_INDEX = 'index'
ACTION_REINDEX = 'reindex'
ACTION_UNINDEX = 'un_index'

# We don't want any other hooks executed before this one right now.  It
# will have an order of -100
_TXN_MGR_ORDER = -100

logger = logging.getLogger("CPSCore.IndexationManager")

class IndexationManager(BeforeCommitSubscriber):
    """Holds data about reindexings to be done."""

    zope.interface.implements(IBeforeCommitSubscriber)

    def __init__(self, mgr):
        """Initialize and register this manager with the transaction."""
        BeforeCommitSubscriber.__init__(self, mgr, order=_TXN_MGR_ORDER)
        self._queue = []
        self._infos = {}

    def push(self, ob, idxs=None, with_security=False, action=ACTION_INDEX):
        """Add / update an object to reindex or unindex to the reindexing queue.

        Copes with security reindexation as well.
        """

        # Do not push anything if the subscriber is not enabled
        # When the manager is disabled it won't queue anything. It means, it
        # can be deactiveted for a while, thus won't queue, and then be
        # activated again and start queuing again.
        if not self.enabled:
            logger.debug("is DISABLED. object %r won't be processed", ob)
            return

        if self.isSynchronous():
            logger.debug("Doing %s on object %r", action, ob)
            self.process(action, ob, idxs=idxs, secu=with_security)
            return

        logger.debug("queue object %r idxs=%s secu=%s"
                     % (ob, idxs, with_security))

        # Compute a key for ob. id() is not enough when cut and paste
        # <id_of_ob, rpath>
        rpath = '/'.join(ob.getPhysicalPath())[1:]
        i = (id(aq_base(ob)), rpath) # XXX should use security manager too
        if action == ACTION_UNINDEX:
            self.pushUnIndex(i, ob)
        else:
            self.pushIndex(action, i, ob,
                           idxs=idxs, with_security=with_security)

    def pushIndex(self, action, i, ob, idxs=None, with_security=False):
        info = self._infos.get(i)
        if info is None:
            info = {
                'action': action,
                'object': ob,
                'idxs': idxs,
                'secu': with_security,
                }
            self._queue.append(i)
            self._infos[i] = info
        elif info['action'] == ACTION_UNINDEX:
            # me must consider this as a full indexing
            self._infos[i] = dict(action=ACTION_REINDEX, object=ob, idxs=[],
                                  secu=with_security)
            self._queue.remove(i)
            self._queue.append(i)
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

        logger.debug("info %r", info)

    def pushUnIndex(self, i, ob):
        """Schedule for unindexing or cancels scheduled indexing."""

        info = self._infos.get(i)
        if info is None: # first call about ob in this txn
            self._infos[i] = dict(action=ACTION_UNINDEX, object=ob)
            self._queue.append(i)
        elif info['action'] == ACTION_INDEX:
            # creation and destruction in the same txn, just unschedule
            del self._infos[i]
        elif info['action'] == ACTION_REINDEX:
            # still needs to be removed
            info['action'] = ACTION_UNINDEX
            self._queue.remove(i)
            self._queue.append(i)

    def __call__(self):
        """Called when transaction commits.

        Does the actual indexing work.
        """

        # At this point, we start processing the queue. If any further
        # indexing happen during this, it still has to be treated.

        # Currently the data structures are such that this is not needed
        # (see unit tests).
        #del_indexation_manager()

        logger.debug("__call__")

        for i in self._queue:
            info = self._infos.pop(i, None)
            if info is None:
                # cancelled by later unindexing
                continue

            logger.debug("__call__ processing %r" % info)
            self.process(info.pop('action'), info.pop('object'), **info)

        self._queue = [] # for what it matters

        logger.debug("__call__ done")

    def processIndex(self, ob, idxs, secu):
        """Process an object, to reindex it."""
        # The object may have been removed from its container since,
        # even if the value we have is still wrapped.
        # Re-acquire it from the root
        # GR: not likely now that manager treats unindexing as well, but
        # might still be good for robustness
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

    def processUnIndex(self, ob):
        """unindexes the object.

        We are pretty sure at this point that the object is still indexed
        """
        getToolByName(ob, 'portal_catalog').unindexObject(ob)

    def process(self, action, ob, idxs=None, secu=None):
        if action == ACTION_UNINDEX:
            self.processUnIndex(ob)
        else:
            self.processIndex(ob, idxs, secu)


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
        mgr = IndexationManager(get_before_commit_subscribers_manager())
        setattr(txn, _TXN_MGR_ATTRIBUTE, mgr)
    return mgr
