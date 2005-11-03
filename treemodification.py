# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""Tree Modification

This module deals with trees, and how they are modified using a set of
simple add/modify/delete operations.

Its goal is to get a minimal representation on how to get from one tree
to another, by simplifying redundant operations. We're only interested
in the state as it exists in the final tree. This is useful to lazily
replay changes to a master tree, without doing useless operations.

Nodes in the tree are addressed using a sequence, usually a tuple, which
represents a path.

The operations available are

 - ``ADD``: add a node (which may have subnodes),
 - ``REMOVE``: remove a node and all its subnodes,
 - ``MODIFY``: modify a node, don't touch subnodes.

Operations that modify a node and all its subnodes are treated as
``ADD``, which means that if a node already exists ``ADD`` will just
replace it.


Tests
=====

Setup and basic tests.
We'll use strings for sequence, it's easier to read::

  >>> from CPSCore.treemodification import ADD, REMOVE, MODIFY
  >>> from CPSCore.treemodification import TreeModification

  >>> TreeModification([])
  TreeModification([])
  >>> TreeModification([(ADD, 'A')])
  TreeModification([(ADD, 'A')])
  >>> tree = TreeModification([(ADD, 'A'), (ADD, 'B')])
  >>> tree.do(ADD, 'C')
  >>> tree.do(ADD, 'D')
  >>> len(tree) # order-dependent
  4

Simple optimizations::

  >>> TreeModification([(ADD, 'A'), (ADD, 'A')])
  TreeModification([(ADD, 'A')])

  >>> TreeModification([(REMOVE, 'A'), (ADD, 'A')])
  TreeModification([(ADD, 'A')])

  >>> TreeModification([(ADD, 'A'), (REMOVE, 'A')])
  TreeModification([(REMOVE, 'A')])

  >>> TreeModification([(MODIFY, 'A'), (MODIFY, 'A')])
  TreeModification([(MODIFY, 'A')])

If you add a node and remove one of its subnode, it's the same as just
adding the node in its final state::

  >>> TreeModification([(ADD, 'A'), (REMOVE, 'AB')])
  TreeModification([(ADD, 'A')])

  >>> TreeModification([(ADD, 'A'), (REMOVE, 'A'), (ADD, 'A')])
  TreeModification([(ADD, 'A')])

If you add something and later add something higher, only the last is
kept::

  >>> TreeModification([(ADD, 'AB'), (ADD, 'A')])
  TreeModification([(ADD, 'A')])

But not for modifies::

  >>> tree = TreeModification([(ADD, 'AB'), (MODIFY, 'A')])
  >>> len(tree) # order-dependent
  2

If you modify and later add, only add is kept::

  >>> TreeModification([(MODIFY, 'A'), (ADD, 'A')])
  TreeModification([(ADD, 'A')])

If you modify and later remove, only add is kept::

  >>> TreeModification([(MODIFY, 'A'), (REMOVE, 'A')])
  TreeModification([(REMOVE, 'A')])

You can't have a modify or add under something that's been removed::

  >>> TreeModification([(REMOVE, 'A'), (ADD, 'AB')])
  Traceback (most recent call last):
  ...
  TreeModificationError: ADD 'AB' after REMOVE 'A'
  >>> TreeModification([(REMOVE, 'A'), (MODIFY, 'AB')])
  Traceback (most recent call last):
  ...
  TreeModificationError: MODIFY 'AB' after REMOVE 'A'
  >>> TreeModification([(REMOVE, 'A'), (MODIFY, 'A')])
  Traceback (most recent call last):
  ...
  TreeModificationError: MODIFY 'A' after REMOVE 'A'

And you can't remove something that's sure to not exist anymore::

  >>> TreeModification([(REMOVE, 'A'), (REMOVE, 'AB')])
  Traceback (most recent call last):
  ...
  TreeModificationError: REMOVE 'AB' after REMOVE 'A'

  >>> TreeModification([(REMOVE, 'A'), (REMOVE, 'A')])
  Traceback (most recent call last):
  ...
  TreeModificationError: REMOVE 'A' after REMOVE 'A'

Of course all this is used with tuple paths in real life::

  >>> TreeModification([(ADD, ('root', 'bob')), (ADD, ('root',))])
  TreeModification([(ADD, ('root',))])


Info mapping
------------

You can pass an additional ``info`` mapping when you do a tree
operation. The purpose of this information is to specify in more detail
the type of operation done. Its semantics is up to the application.:

  >>> TreeModification([(ADD, 'A', {'foo': True})])
  TreeModification([(ADD, 'A', {'foo': True})])

Remember that ``info`` is additional semantics about the operation done,
and ADD always takes precedence over MODIFY, so if a MODIFY is done
after an ADD, the ADD is kept, with its info::

  >>> TreeModification([(ADD, 'A', {'foo': 1}), (MODIFY, 'A', {'bar': 2})])
  TreeModification([(ADD, 'A', {'foo': 1})])

When doing several ADD or REMOVE operations on a node, the last ``info``
always wins::

  >>> TreeModification([(ADD, 'A', {'foo': 1}), (ADD, 'A', {'bar': 2})])
  TreeModification([(ADD, 'A', {'bar': 2})])
  >>> TreeModification([(ADD, 'A', {'foo': 1}), (REMOVE, 'A', {'gee': 3})])
  TreeModification([(REMOVE, 'A', {'gee': 3})])
  >>> TreeModification([(REMOVE, 'A', {'foo': 1}), (ADD, 'A', {'hah': 4})])
  TreeModification([(ADD, 'A', {'hah': 4})])

Info merging
------------

The only interesting use case is when several MODIFY operations are made
in a row on the same node. Then, their ``info`` mappings are merged::

  >>> tree = TreeModification([(MODIFY, 'A', {'foo': 1}),
  ...                          (MODIFY, 'A', {'bar': 2})])
  >>> list(tree.get()) == [(MODIFY, 'A', {'foo': 1, 'bar': 2})]
  True

For some specific application use cases, it's possible to override the
default merging method to make it do whatever is needed::

  >>> def myMergeInfo(old, new):
  ...     return {'n': old['n']+2*new['n']}

  >>> tree = TreeModification(mergeModifyInfo=myMergeInfo)
  >>> tree.do(MODIFY, 'A', {'n': 24})
  >>> tree.do(MODIFY, 'A', {'n': 9})
  >>> tree
  TreeModification([(MODIFY, 'A', {'n': 42})])
  >>> tree.do(MODIFY, 'A', {'n': 4})
  >>> tree
  TreeModification([(MODIFY, 'A', {'n': 50})])

A more realistic use case would be to have "light" and "complex"
modifications, where "complex" takes precedence over "light"::

  >>> def complexMerge(old, new):
  ...     return {'complex': old['complex'] or new['complex']}

  >>> tree = TreeModification(mergeModifyInfo=complexMerge)
  >>> tree.do(MODIFY, 'A', {'complex': False})
  >>> tree.do(MODIFY, 'A', {'complex': False})
  >>> tree
  TreeModification([(MODIFY, 'A', {'complex': False})])
  >>> tree.do(MODIFY, 'A', {'complex': True})
  >>> tree
  TreeModification([(MODIFY, 'A', {'complex': True})])
  >>> tree.do(MODIFY, 'A', {'complex': False})
  >>> tree
  TreeModification([(MODIFY, 'A', {'complex': True})])


"""

class TreeModificationError(Exception):
    """Exception raised for impossible tree operations."""

# Tree operations
ADD = 0
REMOVE = 1
MODIFY = 2
# Internal to the tree representation
_SEEN = 3

printable_op = {
    ADD: 'ADD',
    REMOVE: 'REMOVE',
    MODIFY: 'MODIFY',
    _SEEN: '_SEEN',
    }.get


class TreeModification(object):
    """Represents the optimized list of changes that were applied to a tree.
    """

    def __init__(self, ops=None, mergeModifyInfo=None):
        self.clear()
        self._mergeModifyInfo = mergeModifyInfo
        if ops is not None:
            for args in ops:
                self.do(*args)

    def clear(self):
        """Clear the tree."""
        self._tree = {}
        self._ops = None
        self._path_is_string = False # tuple by default

    def __repr__(self):
        res = []
        for op, path, info in self.get():
            if not info:
                res.append('(%s, %r)' % (printable_op(op), path))
            else:
                res.append('(%s, %r, %r)' % (printable_op(op), path, info))
        return 'TreeModification(['+', '.join(res)+'])'

    def __len__(self):
        return len(self.get())

    def get(self):
        """Return the optimized tree, as a list of operations."""
        if self._ops is None:
            ops = []
            self._recurse((), self._tree, ops)
            self._ops = tuple(ops)
        return self._ops

    def _recurse(self, prefix, tree, ops):
        for step, value in tree.items():
            op, info, subtree = value
            path = prefix + (step,)
            if op is not _SEEN:
                if self._path_is_string:
                    jpath = ''.join(path)
                else:
                    jpath = path
                ops.append((op, jpath, info))
            self._recurse(path, subtree, ops)

    def mergeModifyInfo(self, old, new):
        """Default modify merger.

        If several ``MODIFY`` are applied successively, their ``info``
        values get merged using this method, which by default simply
        calls ``update()``.
        """
        if self._mergeModifyInfo is not None:
            return self._mergeModifyInfo(old, new)
        else:
            # Default merging
            res = {}
            res.update(old)
            res.update(new)
            return res

    def do(self, op, path, info=None):
        """Do an operation on the tree.

        ``op`` can be one of ``ADD``, ``REMOVE`` or ``MODIFY``.

        ``path`` is a sequence representing a node.

        ``info`` is a mapping, or None. It represents additional
        information about ``MODIFY`` operations
        """
        if not path:
            return TreeModificationError("Empty path forbidden")
        if info is None:
            info = {}
        self._ops = None
        tree = self._tree
        if not tree and isinstance(path, basestring):
            self._path_is_string = True
        # Walk the path to our node.
        for i, step in enumerate(path[:-1]):
            if step in tree:
                old_op, old_info, subtree = tree[step]
                if old_op == REMOVE:
                    # REMOVE higher in the tree, error
                    raise TreeModificationError(
                        "%s %r after REMOVE %r" %
                        (printable_op(op), path, path[:i+1]))
                elif old_op == ADD:
                    # ADD higher in the tree, stop
                    return
            else:
                # We've never been here, add an intermediate node
                subtree = {}
                tree[step] = (_SEEN, None, subtree)
            tree = subtree
        # Last step
        step = path[-1]
        if step in tree:
            old_op, old_info, subtree = tree[step]
            if old_op == REMOVE and op in (REMOVE, MODIFY):
                raise TreeModificationError(
                    "%s %r after REMOVE %r" %
                    (printable_op(op), path, path))
            elif op in (ADD, REMOVE):
                # ADD or REMOVE override older ops and the subtree
                tree[step] = (op, info, {})
            elif old_op == ADD:
                # MODIFY after ADD, ignore
                pass
            elif old_op == _SEEN:
                # MODIFY after _SEEN, replace op
                tree[step] = (op, info, subtree)
            else: # old_op == MODIFY
                # MODIFY after MODIFY, merge infos
                new_info = self.mergeModifyInfo(old_info, info)
                tree[step] = (op, new_info, subtree)
        else:
            tree[step] = (op, info, {})
