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
  >>> tree
  TreeModification([(ADD, 'A'), (ADD, 'B'), (ADD, 'C'), (ADD, 'D')])

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

  >>> TreeModification([(ADD, 'AB'), (MODIFY, 'A')])
  TreeModification([(ADD, 'AB'), (MODIFY, 'A')])

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

printable_op = {
    ADD: 'ADD',
    REMOVE: 'REMOVE',
    MODIFY: 'MODIFY',
    }.get


# Internal decision table:
_STOP, _FORGET, _CONT, _ERROR = range(4)
# _STOP: stop trying, something overrides us anyway
# _FORGET: forget the old op (it's overriden), and continue looking
# _CONT: continue looking
# _ERROR: impossible case
_OLD_ABOVE_NEW = 0
_OLD_EQ_NEW =    1
_OLD_UNDER_NEW = 2
_UNRELATED =     3
_RULES = {
   #                 (>:above)         (<:under)
   # old_op  op       old>new  old=new  old<new  unrel
    (ADD,    ADD   ): [_STOP,  _FORGET, _FORGET, _CONT],
    (ADD,    REMOVE): [_STOP,  _FORGET, _FORGET, _CONT],
    (ADD,    MODIFY): [_STOP,  _STOP,   _CONT  , _CONT],
    (REMOVE, ADD   ): [_ERROR, _FORGET, _FORGET, _CONT],
    (REMOVE, REMOVE): [_ERROR, _ERROR,  _FORGET, _CONT],
    (REMOVE, MODIFY): [_ERROR, _ERROR,  _CONT  , _CONT],
    (MODIFY, ADD   ): [_CONT,  _FORGET, _FORGET, _CONT],
    (MODIFY, REMOVE): [_CONT,  _FORGET, _FORGET, _CONT],
    (MODIFY, MODIFY): [_CONT,  _FORGET, _CONT  , _CONT],
    }

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
        self._ops = []

    def __repr__(self):
        res = []
        for op, path in self._ops:
            res.append('(%s, %r)' % (printable_op(op), path))
        return 'TreeModification(['+', '.join(res)+'])'

    def get(self):
        """Return the optimized tree, as a list of operations."""
        return self._ops[:]

    def do(self, op, path):
        """Do an operation on the tree.

        ``op`` can be one of ``ADD``, ``REMOVE`` or ``MODIFY``.
        ``path`` is a sequence representing a node.
        """
        ops = []
        len_path = len(path)
        for old_op, old_path in self._ops:
            if old_path == path:
                case = _OLD_EQ_NEW
            else:
                if old_path[:len_path] == path:
                    case = _OLD_UNDER_NEW
                elif path[:len(old_path)] == old_path:
                    case = _OLD_ABOVE_NEW
                else:
                    case = _UNRELATED
            action = _RULES[(old_op, op)][case]
            if action == _STOP:
                return
            elif action == _ERROR:
                raise TreeModificationError(
                    "%s %r after %s %r" % (printable_op(op), path,
                                           printable_op(old_op), old_path))
            elif action == _FORGET:
                continue
            else: # action == _CONT
                ops.append((old_op, old_path))
        ops.append((op, path))
        self._ops = ops

