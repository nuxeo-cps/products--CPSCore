# -*- coding: iso-8859-15 -*-
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

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder

from Products.CPSCore.ObjectRepositoryTool import ObjectRepositoryTool

from dummy import DummyContent

def constructContent(self, type_name, id, *args, **kw):
    assert type_name == 'DummyContent'
    self._setObject(id, DummyContent(id, *args, **kw))

constructContent_old = ObjectRepositoryTool.constructContent

class ObjectRepositoryToolTests(SecurityRequestTest):
    """Test object repository ."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = Folder()
        self.root.id = 'root'
        root = self.root

        ObjectRepositoryTool.constructContent = constructContent
        ortool = ObjectRepositoryTool()
        root._setObject('portal_repository', ortool)


    def tearDown( self ):
        #    SecurityRequestTest.tearDown(self)
        ObjectRepositoryTool.constructContent = constructContent_old

    ##########

    def test_add_del(self):
        ortool = self.root.portal_repository

        # Empty
        self.assertEquals(ortool.listAll(), [])
        self.assertEquals(ortool.listDocids(), [])

        # Add one
        ortool.createRevision('123', 'DummyContent')
        items = ortool.listAll()
        self.assertEquals(len(items), 1)
        self.assertEquals(items, [('123', 1),])
        self.assertEquals(ortool.listDocids(), ['123'])

        # Add another version
        ortool.createRevision('123', 'DummyContent')
        items = ortool.listAll()
        # Items are sorted by implementation, but not by contract
        items.sort() 
        self.assertEquals(len(items), 2)
        self.assertEquals(items, [('123', 1), ('123', 2)])

        # Remove non-existent
        self.assertRaises(KeyError, ortool.delObjectRevision, '123', 9)

        # Add more
        ortool.createRevision('ahah', 'DummyContent')
        ortool.createRevision('ahah', 'DummyContent')
        items = ortool.listAll()
        items.sort()
        self.assertEquals(len(items), 4)
        self.assertEquals(items, [('123', 1), ('123', 2),
                                   ('ahah', 1), ('ahah', 2)])
        self.assertEquals(ortool.listDocids(), ['123', 'ahah'])

        # Remove all versions of one
        ortool.delObjectRevisions('123')
        items = ortool.listAll()
        items.sort()
        self.assertEquals(len(items), 2)
        self.assertEquals(items, [('ahah', 1), ('ahah', 2)])
        self.assertEquals(ortool.listDocids(), ['ahah'])

        # Remove rest one by one
        ortool.delObjectRevision('ahah', 1)
        self.assertEqual(ortool.listAll(), [('ahah', 2)])
        self.assertEquals(ortool.listDocids(), ['ahah'])
        ortool.delObjectRevision('ahah', 2)
        self.assertEqual(ortool.listAll(), [])
        self.assertEquals(ortool.listDocids(), [])


    def test_ObjectVersions(self):
        ortool = self.root.portal_repository
        ortool.createRevision('foo', 'DummyContent', 'bar')
        ortool.createRevision('foo', 'DummyContent', 'moo')

        # Check getObjectRevision
        self.assertRaises(KeyError, ortool.getObjectRevision, 'foo', 99)
        ob = ortool.getObjectRevision('foo', 1)
        self.assertEqual(ob.getData(), 'bar')
        ob = ortool.getObjectRevision('foo', 2)
        self.assertEqual(ob.getData(), 'moo')

        # Check listRevisions
        version_infos = ortool.listRevisions('foo')
        version_infos.sort()
        self.assertEquals(version_infos, [1, 2])
        self.assertEquals(ortool.listRevisions('notarepoid'), [])

        # Check listAll, listDocids
        self.assertEquals(ortool.listAll(), [('foo', 1), ('foo', 2)])
        self.assertEquals(ortool.listDocids(), ['foo'])

    def test_docidMethods(self):
        ortool = self.root.portal_repository

        docid = ortool.getFreeDocid()
        # check that docid actually exists and is a number
        self.assert_(docid.isdigit())
        # check that first revision for a given docid is __0001
        self.assertEquals(ortool.getFreeRevision(docid), 1)
        # check that next revision for a docid which already
        # has revision __0002 in the repository is __0003
        ortool._tree[docid + '__0002'] = 'dummy'
        self.assertEquals(ortool.getFreeRevision(docid), 3)
        # check that next revision for a docid which already
        # has revision __9998 in the repository is __9999
        ortool._tree[docid + '__9998'] = 'dummy'
        self.assertEquals(ortool.getFreeRevision(docid), 9999)
        # check listRevisions
        revs = ortool.listRevisions(docid)
        for rev in (2, 9998):
            self.assert_(rev in revs)


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(ObjectRepositoryToolTests)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
