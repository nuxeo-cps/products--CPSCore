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

import os, sys, unittest

from Products.CPSCore.BlockingIndex.BlockingIndex import makeBlockCanonical
from Products.CPSCore.BlockingIndex.BlockingIndex import makeKeywordCanonical
from Products.CPSCore.BlockingIndex.BlockingIndex import BlockingIndex


class DummyObject:
    meta_type = 'dummy_object'

    def __init__(self, id, aru):
        self.id = id
        self.aru = tuple(aru)

    def getId():
        return self.id

    def allowedRolesAndUsersBlocking(self):
        return self.aru

    def __str__( self ):
        return '<DummyObject %s>' % self.id

    __repr__ = __str__


class TestBlockingIndex(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self._index = BlockingIndex()

    def test_makeBlockCanonical(self):
        mc = makeBlockCanonical
        self.assertEqual(mc([]), [])
        self.assertEqual(mc(['A', 'B', 'C']), [['A', 'B', 'C']])
        self.assertEqual(mc(['B', 'C', 'A']), [['A', 'B', 'C']])
        self.assertEqual(mc(['B', 'C', 'A', 'A', 'C']), [['A', 'B', 'C']])
        self.assertEqual(mc(['A', 'B', '', 'C']), [['A', 'B', 'C']])
        self.assertEqual(mc(['-A', '-B', 'C']), [[], ['A', 'B'], ['C']])
        self.assertEqual(mc(['A', '-B', 'C']), [['A'], ['B'], ['C']])
        self.assertEqual(mc(['A', '-B', '-C']), [['A'], ['B', 'C']])
        self.assertEqual(mc(['A', '-B', '', '-C', '-B']), [['A'], ['B', 'C']])
        self.assertEqual(mc(['A', '-B', '-', 'C']), [['A'], ['', 'B'], ['C']])
        self.assertEqual(mc(['A', '-B', '-', '-C']), [['A'], ['', 'B', 'C']])
        self.assertEqual(mc(['B', 'A', '-C', 'E', 'D', '-F']),
                         [['A', 'B'], ['C'], ['D', 'E'], ['F']])

    def test_makeKeywordCanonical(self):
        mc = makeKeywordCanonical
        self.assertEqual(mc([]), [])
        self.assertEqual(mc([['A', 'B', 'C']]), ['A', 'B', 'C'])
        self.assertEqual(mc([[], ['A', 'B'], ['C']]), ['-A', '-B', 'C'])
        self.assertEqual(mc([['A'], ['B'], ['C']]), ['A', '-B', 'C'])
        self.assertEqual(mc([['A'], ['B', 'C']]), ['A', '-B', '-C'])
        self.assertEqual(mc([['A'], ['', 'B'], ['C']]), ['A', '-', '-B', 'C'])
        self.assertEqual(mc([['A'], ['', 'B', 'C']]), ['A', '-', '-B', '-C'])
        self.assertEqual(mc([['A', 'B'], ['C'], ['D', 'E'], ['F']]),
                         ['A', 'B', '-C', 'D', 'E', '-F'])

    def testEmpty(self):
        index = self._index
        self.assertEqual(len(index) ,0)
        self.assertEqual(index.getEntryForObject(1234), None)

    def testAddRemove(self):
        index = self._index
        ob = DummyObject('a', ['Foo', 'Bar', '-Baz', 'Goo'])
        index.index_object(1234, ob)
        self.assertEqual(len(index), 1)
        ob2 = DummyObject('a', ['Foo', '-Bar', '-Baz', 'Goo'])
        index.index_object(456, ob2)
        self.assertEqual(len(index), 2)
        index.unindex_object(1234)
        self.assertEqual(len(index), 1)
        index.unindex_object(456)
        self.assertEqual(len(index), 0)

    def xxxtestUnIndex(self):
        self._populateIndex()
        self.assertEqual(self._index.numObjects(), 18)

        for k in self._values.keys():
            self._index.unindex_object(k)

        self.assertEqual(self._index.numObjects(), 0)
        self.assertEqual(len(self._index._index), 0)
        self.assertEqual(len(self._index._unindex), 0)


def test_suite():
    return unittest.makeSuite(TestBlockingIndex)

if __name__=="__main__":
    unittest.TextTestRunner().run(test_suite())
