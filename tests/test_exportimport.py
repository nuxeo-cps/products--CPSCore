# (C) Copyright 2006 Nuxeo SAS <http://nuxeo.com>
# Authors:
# - Anahide Tchertchian <at@nuxeo.com>
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
"""Tests for the CPScore export/import mechanism
"""

import os
import unittest
from Acquisition import Implicit, aq_parent, aq_inner
from OFS.Folder import Folder
from Testing import ZopeTestCase
from Products.CPSUtil.testing.genericsetup import ExportImportTestCase

ZopeTestCase.installProduct('CPSCore')

TEST_DIR = os.path.split(__file__)[0]

# generic class giving info needed by tree caches
class FakeFolder(Folder):

    meta_type = "Folder Meta Type"

    def getFolderInfo(self, doc):
        return {}

    def get_local_group_roles(self):
        return ()

class CachedFolder(FakeFolder):

    portal_type = "Cached Folder Type"

class UnCachedFolder(FakeFolder):

    portal_type = "Uncached Folder Type"


class FakeUrlTool(Implicit):

    def __init__(self):
        self.id = 'portal_url'

    def getPortalObject(self):
        return aq_parent(aq_inner(self))


class TreesToolExportImportTest(ExportImportTestCase):

    def afterSetUp(self):
        ExportImportTestCase.afterSetUp(self)
        # add needed url tool
        self.folder._setObject('portal_url', FakeUrlTool())
        # profiles registration
        self.registerProfile('trees', "Trees", "Minimal profile with trees",
                             'tests/profiles/minimal_trees', 'CPSCore')
        # create the root of the tree cache
        self.folder._setObject("root", CachedFolder("root"))
        self.real_root = self.folder.root

    def beforeTearDown(self):
        ExportImportTestCase.beforeTearDown(self)
        self.clearProfileRegistry()
        del self.real_root

    def test_import(self):
        self.assertEquals('portal_trees' not in self.folder.objectIds(), True)
        self.importProfile('CPSCore:trees')

        # check portal_trees
        self.assertEquals('portal_trees' in self.folder.objectIds(), True)
        ttool = self.folder.portal_trees
        self.assertEquals(ttool.meta_type, 'CPS Trees Tool')

        # check tree caches
        self.assertEquals(ttool.objectIds(), ['root'])
        tree_root = ttool.root
        # check properties
        property_items = [
            ('title', "Bloody Root"),
            ('root', 'root'),
            ('type_names', ('Cached Folder Type',)),
            ('meta_types', ('Folder Meta Type',)),
            ('excluded_rpaths', ()),
            ('info_method', 'getFolderInfo'),
            ('terminal_nodes', ()),
            ]
        self.assertEquals(tree_root.propertyItems(), property_items)

        # root is filled with existing root
        self.assertEquals(list(tree_root._infos), ['root'])


    def test_import_with_content(self):
        # create content that will have to be indexed (or not) in the tree
        # cache
        self.real_root._setObject("cached", CachedFolder("cached"))
        self.real_root._setObject("uncached", UnCachedFolder("uncached"))

        # import the profile, cache will be initialized
        self.importProfile('CPSCore:trees')
        # check tree cache infos
        self.assertEquals('portal_trees' in self.folder.objectIds(), True)
        ttool = self.folder.portal_trees
        self.assertEquals('root' in ttool.objectIds(), True)
        tree_root = ttool.root
        infos = tree_root._infos
        self.assertEquals(list(infos), ['root', 'root/cached'])

        # import again (without purging): tree should not be rebuilt
        self.importProfile('CPSCore:trees', purge_old=False)
        new_infos = tree_root._infos
        self.assertEquals(infos, new_infos)

        # change properties, need to rebuild manually
        new_type_names = ('Cached Folder Type', 'Uncached Folder Type')
        tree_root.manage_changeProperties(type_names=new_type_names)
        self.assertEquals(list(new_infos),
                          ['root', 'root/cached'])
        tree_root.rebuild()
        new_infos = tree_root._infos
        self.assertEquals(list(new_infos),
                          ['root', 'root/cached', 'root/uncached'])

        # import again (without purging)
        self.importProfile('CPSCore:trees', purge_old=False)
        # check tree cache properties are reset
        property_items = [
            ('title', "Bloody Root"),
            ('root', 'root'),
            ('type_names', ('Cached Folder Type',)),
            ('meta_types', ('Folder Meta Type',)),
            ('excluded_rpaths', ()),
            ('info_method', 'getFolderInfo'),
            ('terminal_nodes', ()),
            ]
        self.assertEquals(tree_root.propertyItems(), property_items)
        # check tree cache infos, tree has been rebuilt
        newer_infos = tree_root._infos
        self.assertNotEquals(new_infos, newer_infos)
        self.assertEquals(list(newer_infos), ['root', 'root/cached'])

    def test_export(self):
        self.importProfile('CPSCore:trees')
        toc_list = [
            'export_steps.xml',
            'import_steps.xml',
            'trees/root.xml',
            'trees.xml',
           ]
        self._checkExportProfile(os.path.join(
                TEST_DIR, 'profiles', 'minimal_trees'), toc_list)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreesToolExportImportTest),
        ))

