# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author: Florent Guillaume <fg@nuxeo.com>
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
"""BlockingIndex

"""

from __future__ import nested_scopes

from zLOG import LOG, DEBUG, ERROR

from types import ListType, TupleType, IntType
from Globals import InitializeClass, DTMLFile, Persistent
from AccessControl import ClassSecurityInfo

from OFS.SimpleItem import SimpleItem

from Products.PluginIndexes import PluggableIndex
from Products.PluginIndexes.common.util import parseIndexRequest
from Products.PluginIndexes.common import safe_callable

from Globals import DTMLFile
from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from BTrees.IIBTree import IITreeSet
from BTrees.Length import Length


_marker = []


def makeBlockCanonical(keywords):
    """Turn a list of blocking keywords into a canonical form.

    Turns something of the form
      ['A', 'B', '-C', 'D', 'E', '-F']
    into
      [['A', 'B'], ['C'], ['D', 'E'], ['F']]

    Sorts them, and removes duplicates.
    """
    values = list(keywords)
    res = []
    acc = {}
    positive = 1
    while values:
        v = values.pop(0)
        if not v:
            # Ignore empty values
            continue
        if v[0] == '-':
            v = v[1:]
            if positive:
                positive = 0
                res.append(acc)
                acc = {}
        else:
            if not positive:
                positive = 1
                res.append(acc)
                acc = {}
        acc[v] = None
    if acc:
        res.append(acc)
    result = []
    for acc in res:
        block = acc.keys()
        block.sort()
        result.append(block)
    return result


def makeKeywordCanonical(blocks):
    """Turn canonical blocks back into a normal keyword list."""
    res = []
    prefix = '-'
    for block in blocks:
        if prefix:
            prefix = ''
        else:
            prefix = '-'
        for v in block:
            res.append(prefix+v)
    return res


class BlockingIndex(Persistent, SimpleItem):
    """Blocking Index.

    Stores positive/negative lists of keywords.

    """
    meta_type = 'BlockingIndex'

    query_options = ('query',)

    indexed_attr = 'allowedRolesAndUsersBlocking'

    def __init__(self):
        self.clear()
        self._length = Length(0)

    #  PluggableIndexInterface

    def clear(self):
        """Clear the index."""
        self._index = OOBTree() # keyword -> row of rid (int or IITreeSet)
        # In _index, the value for the key None is an OOBTree
        # for blocking indexes, mapping keyword -> subindex
        self._unindex = IOBTree() # rid -> blocks

    def index_object(self, rid, ob, threshold=None):
        """Index an object."""
        blocks = self._getValueFor(ob)

        if self._unindex.has_key(rid):
            self.unindex_object(rid)

        # Forward entry
        self._insertForward(rid, blocks)

        # Reverse entry
        self._unindex[rid] = blocks
        self._length.change(1)

    def unindex_object(self, rid):
        """Unindex an object."""
        if not self._unindex.has_key(rid):
            LOG('BlockingIndex', ERROR,
                "Attempt to unindex nonexistent document with id %s" % rid)
            return

        blocks = self._unindex[rid]
        self._removeForward(rid, blocks)

        del self._unindex[rid]
        self._length.change(-1)

    def _apply_index(self, request, cid=''):
        """Apply the index to query parameters given in the argument.

        Called by ZCatalog's search method.
        """
        YYY

    def getEntryForObject(self, rid, default=_marker):
        """Get all the information we have on a rid."""
        if default is _marker:
            return self._unindex.get(rid)
        else:
            return self._unindex.get(rid, default)

    def getIndexSourceNames(self):
        """ return names of indexed attributes """
        return (self.indexed_attr,)

    def numObjects(self):
        """ return the number of indexed objects"""
        return self._length()

    # private

    def __len__(self):
        return self._length()

    def _getValueFor(self, ob):
        """Get the value to index for the object."""
        value = getattr(ob, self.indexed_attr, ())
        if safe_callable(value):
            value = value()
        if (not isinstance(value, ListType) and
            not isinstance(value, TupleType)):
            value = [value]
        return makeBlockCanonical(value)

    def _insertForward(self, rid, blocks):
        """Insert the entry in the forward indexes.

        Each negative keyword triggers use of an additional index.
        """
        contexts = [[self._index, None]]
        while blocks:
            # Positive assertions
            block = blocks.pop(0)
            for context in contexts:
                index, setindex = context
                if index is None:
                    # Lazy construction
                    index = OOBTree()
                    context[0] = index # update for blocking pass
                    setindex(index)
                for value in block:
                    row = index.get(value)
                    if row is None:
                        # first value, just store an int
                        index[value] = rid
                    elif isinstance(row, IntType):
                        # row was an int, make it a IITreeSet
                        index[value] = IITreeSet((row, rid))
                    else:
                        # extend existing row
                        row.insert(rid)
            if not blocks:
                break
            # Blocking assertions
            block = blocks.pop(0)
            new_contexts = []
            for index, setindex_ in contexts:
                blocking_index = index.get(None)
                if blocking_index is None:
                    blocking_index = OOBTree()
                    index[None] = blocking_index
                for value in block:
                    subindex = blocking_index.get(value)
                    if subindex is None:
                        # Lazy: a subindex for the value will be needed
                        def setindex(ix):
                            blocking_index[value] = ix
                        context = [None, setindex]
                    else:
                        # Got subindex
                        context = [subindex, None]
                    new_contexts.append(context)
            contexts = new_contexts

    #
    # ZMI
    #

    manage_main = DTMLFile('zmi/manageBlockingIndex', globals())
    manage_main._setName('manage_main')

    manage_workspace = manage_main

    manage_options = (
        {'label' : 'Settings', 'action' : 'manage_main'},
        ) + SimpleItem.manage_options

InitializeClass(BlockingIndex)


manage_addBlockingIndexForm = DTMLFile('zmi/addBlockingIndex', globals())

def manage_addBlockingIndex(self, id, REQUEST=None, RESPONSE=None, URL3=None):
    """Add a Blocking Index"""
    return self.manage_addIndex(id, 'BlockingIndex', extra=None,
                                REQUEST=REQUEST, RESPONSE=RESPONSE, URL1=URL3)
