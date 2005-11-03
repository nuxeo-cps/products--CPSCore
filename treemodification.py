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
-----

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

    def __init__(self, ops=None):
        self.clear()
        if ops is not None:
            for op, path in ops:
                self.do(op, path)

    def clear(self):
        """Clear the tree."""
        self._tree = {}
        self._ops = None
        self._path_is_string = False # tuple by default

    def __repr__(self):
        res = []
        for op, path in self.get():
            res.append('(%s, %r)' % (printable_op(op), path))
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
            op, subtree = value
            path = prefix + (step,)
            if op is not _SEEN:
                if self._path_is_string:
                    jpath = ''.join(path)
                else:
                    jpath = path
                ops.append((op, jpath))
            self._recurse(path, subtree, ops)

    def do(self, op, path):
        """Do an operation on the tree.

        ``op`` can be one of ``ADD``, ``REMOVE`` or ``MODIFY``.

        ``path`` is a sequence representing a node.
        """
        if not path:
            return TreeModificationError("Empty path forbidden")
        self._ops = None
        tree = self._tree
        if not tree and isinstance(path, basestring):
            self._path_is_string = True
        # Walk the path to our node.
        for i, step in enumerate(path[:-1]):
            if step in tree:
                old_op, subtree = tree[step]
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
                tree[step] = (_SEEN, subtree)
            tree = subtree
        # Last step
        step = path[-1]
        if step in tree:
            old_op, subtree = tree[step]
            if old_op == REMOVE and op in (REMOVE, MODIFY):
                raise TreeModificationError(
                    "%s %r after REMOVE %r" %
                    (printable_op(op), path, path))
            elif op in (ADD, REMOVE):
                # ADD or REMOVE override older ops and the subtree
                tree[step] = (op, {})
            elif old_op == ADD:
                # MODIFY after ADD, ignore
                pass
            elif old_op == _SEEN:
                # MODIFY after _SEEN, replace op
                tree[step] = (op, subtree)
            else: # old_op == MODIFY
                # MODIFY after MODIFY, ignore
                pass
        else:
            tree[step] = (op, {})
