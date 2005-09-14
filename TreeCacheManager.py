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

from Products.CPSCore.interfaces import IBaseManager
from Products.CPSCore.BaseManager import BaseManager
from Products.CPSCore.TransactionManager import get_transaction_manager

_TXN_MGR_ATTRIBUTE = '_cps_tc_manager'

# Just before the EventManager
_TXN_MGR_ORDER = 0

class TreeCacheManager(BaseManager):
    """Holds data about treecache rebuilts to be done."""

    __implements__ = IBaseManager

    def __init__(self, mgr):
        """Initialize and register this manager with the transaction manager
        """
        BaseManager.__init__(self, mgr, order=_TXN_MGR_ORDER)
        self._queue = {}

    def push(self, tree, event_type, ob, infos):

        if infos is None:
            infos = {}

        if self.isSynchronous():
            LOG("TreeCacheManager", DEBUG,
                "rebuild cache %s for %s on %s with %s"
                %(tree, ob, event_type, infos))
            tree.notify_tree(event_type, ob, infos)
            return

        LOG("TreeCacheManager", DEBUG,
            "queue object %s in cache %s for %s with %s"
            % (ob, tree, event_type, infos))

        # XXX : Here, we can optimize by dealing with the events on
        # the same object
        rpath = '/'.join(ob.getPhysicalPath())[1:]
        i = (id(tree), id(aq_base(ob)), rpath, event_type)
        if i not in self._queue:
            self._queue[i] = (ob, tree, infos)
        else:
            self._queue[i][2].update(infos)

    def __call__(self):
        """Called when transaction commits.

        Does the actual rebuild work
        """

        LOG("TreeCacheManager", DEBUG, "__call__")

        for k, v in self._queue.items():
            LOG("TreeCacheManager", DEBUG,
                "rebuild cache %s for %s on %s with %s"
                %(v[1], v[0], k[3], v[2]))
            v[1].notify_tree(k[3], v[0], v[2])

        self._queue = {}

        LOG("TreeCacheManager", DEBUG, "__call__ done")

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
