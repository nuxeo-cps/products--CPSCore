# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Tests for the object repository
"""

import Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem


class Dummy(SimpleItem):
    def __init__(self, id, data=None):
        self._id = id
        self._data = data

    def getId(self):
        return self._id

    def getData(self):
        return self._data


class ObjectRepositoryToolTests(SecurityRequestTest):
    """Test object repository ."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = Folder()
        self.root.id = 'root'
        root = self.root

        from Products.CPSCore.ObjectRepositoryTool import ObjectRepositoryTool
        ortool = ObjectRepositoryTool()
        root._setObject('portal_repository', ortool)


    #def tearDown( self ):
    #    SecurityRequestTest.tearDown(self)

    ##########

    def test_add_del(self):
        ortool = self.root.portal_repository
        # empty
        self.assertEqual(tuple(ortool.listAll()), ())
        # add one
        ob = Dummy('foo')
        ortool.addObjectVersion(ob, '123', 3)
        self.assertEqual(tuple(ortool.listAll()), (('123', 3),))
        # add another version
        ob = Dummy('baz')
        ortool.addObjectVersion(ob, '123', 5)
        items = ortool.listAll()
        items.sort()
        self.assertEqual(tuple(items), (('123', 3), ('123', 5)))
        # remove non-existent
        self.assertRaises(AttributeError, ortool.delObjectVersion, '123', 9)
        # add more
        ob = Dummy('foo2')
        ortool.addObjectVersion(ob, 'ahah', 0)
        ob = Dummy('baz2')
        ortool.addObjectVersion(ob, 'ahah', 1)
        items = ortool.listAll()
        items.sort()
        self.assertEqual(tuple(items), (('123', 3), ('123', 5),
                                        ('ahah', 0), ('ahah', 1)))
        # remove all versions of one
        ortool.delObject('123')
        items = ortool.listAll()
        items.sort()
        self.assertEqual(tuple(items), (('ahah', 0), ('ahah', 1)))
        # remove rest one by one
        ortool.delObjectVersion('ahah', 0)
        self.assertEqual(tuple(ortool.listAll()), (('ahah', 1),))
        ortool.delObjectVersion('ahah', 1)
        self.assertEqual(tuple(ortool.listAll()), ())

    def test_getObjectVersion(self):
        ortool = self.root.portal_repository
        ob = Dummy('foo', 'bar')
        ortool.addObjectVersion(ob, '123', 3)
        ob = Dummy('baz', 'moo')
        ortool.addObjectVersion(ob, '123', 5)
        self.assertRaises(AttributeError, ortool.getObjectVersion, '123', 99)
        ob = ortool.getObjectVersion('123', 3)
        self.assertEqual(ob.getData(), 'bar')
        ob = ortool.getObjectVersion('123', 5)
        self.assertEqual(ob.getData(), 'moo')

    def test_listVersions(self):
        ortool = self.root.portal_repository
        ob = Dummy('foo')
        ortool.addObjectVersion(ob, '123', 3)
        ob = Dummy('baz')
        ortool.addObjectVersion(ob, '123', 5)
        ob = Dummy('aaa')
        ortool.addObjectVersion(ob, 'ccc', 555)
        # list versions
        version_infos = ortool.listVersions('123')
        version_infos.sort()
        self.assertEqual(tuple(version_infos), (3, 5))
        self.assertEqual(tuple(ortool.listVersions('ccc')), (555,))
        # no such repoid
        self.assertEqual(tuple(ortool.listVersions('notarepoid')), ())

    def test_listRepoIds(self):
        ortool = self.root.portal_repository
        ob = Dummy('foo')
        ortool.addObjectVersion(ob, '123', 3)
        ob = Dummy('baz')
        ortool.addObjectVersion(ob, '123', 5)
        ob = Dummy('aaa')
        ortool.addObjectVersion(ob, 'ccc', 555)
        repoids = ortool.listRepoIds()
        self.assertEqual(tuple(repoids), ('123', 'ccc'))
        # now remove
        ortool.delObjectVersion('123', 3)
        repoids = ortool.listRepoIds()
        repoids.sort()
        self.assertEqual(tuple(repoids), ('123', 'ccc'))
        ortool.delObjectVersion('123', 5)
        self.assertEqual(tuple(ortool.listRepoIds()), ('ccc',))
        ortool.delObjectVersion('ccc', 555)
        self.assertEqual(tuple(ortool.listRepoIds()), ())


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(ObjectRepositoryToolTests)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
