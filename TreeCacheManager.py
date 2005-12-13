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
"""Manager for tree cache that can be delayed until commit time.

Asynchronous by default.
"""

import logging
import transaction
import zope.interface

from Products.CPSCore.interfaces import IBaseManager
from Products.CPSCore.BaseManager import BaseManager
from Products.CPSCore.TransactionManager import get_transaction_manager

from Products.CPSCore.treemodification import TreeModification
from Products.CPSCore.treemodification import printable_op

_TXN_MGR_ATTRIBUTE = '_cps_tc_manager'

# Just before the EventManager
_TXN_MGR_ORDER = 0

logger = logging.getLogger("CPSCore.TreeCacheManager")

class TreeCacheManager(BaseManager):
    """Holds data about treecache rebuilts to be done."""

    zope.interface.implements(IBaseManager)

    def __init__(self, mgr):
        """Initialize and register this manager with the transaction manager
        """
        super(TreeCacheManager, self).__init__(mgr, order=_TXN_MGR_ORDER)
        self.clear()
        self._sync = False

    def clear(self):
        self._trees = {} # modification tree for each cache
        self._caches = {} # caches (keyed by tree path)

    def setSynchronous(self, sync):
        if sync:
            raise ValueError("Can't set TreeCacheManager synchronous")

    def push(self, cache, op, path, info):
        """Push an operation for a tree cache.
        """

        # Do not push anything if the subscriber is not enabled
        # When the manager is disabled it won't queue anything. It means, it
        # can be deactiveted for a while, thus won't queue, and then be
        # activated again and start queuing again.
        if not self._status:
            logger.debug(
                "is DISABLED. push for %s: %s %s %r will *not* be done"
                % (cache.getId(), printable_op(op), '/'.join(path), info))
            return
        
        logger.debug("push for %s: %s %s %r"
                     % (cache.getId(), printable_op(op), '/'.join(path), info))
        cache_path = cache.getPhysicalPath()
        if cache_path not in self._trees:
            tree = TreeModification()
            self._trees[cache_path] = tree
            self._caches[cache_path] = cache
        else:
            tree = self._trees[cache_path]
        tree.do(op, path, info)

    def _getModificationTree(self, cache):
        """Debugging: get the modification tree for a tree cache.
        """
        return self._trees[cache.getPhysicalPath()]

    def __call__(self):
        """Called when transaction commits.

        Does the actual rebuild work
        """
        for cache_path, tree in self._trees.items():
            cache = self._caches[cache_path]
            logger.debug("replaying for cache %s" % cache.getId())
            cache.updateTree(tree)
        self.clear()

def get_treecache_manager():
    """Get the treecache manager.

    Creates it if needed.
    """
    txn = transaction.get()
    mgr = getattr(txn, _TXN_MGR_ATTRIBUTE, None)
    if mgr is None:
        mgr = TreeCacheManager(get_transaction_manager())
        setattr(txn, _TXN_MGR_ATTRIBUTE, mgr)
    return mgr
