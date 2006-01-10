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
"""Tests for catalog upgrade (3.3.5 to 3.3.6).
"""

import unittest
from Testing import ZopeTestCase

from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem
from Products.CMFCore.CatalogTool import CatalogTool
from Products.ZCTextIndex.Lexicon import Splitter
from Products.ZCTextIndex.Lexicon import CaseNormalizer
from Products.ZCTextIndex.Lexicon import StopWordRemover
from Products.CMFCore.utils import SimpleRecord

ZopeTestCase.installProduct('ZCTextIndex', quiet=1)


class FakeObject(SimpleItem):
    title = 'fake'
    def __init__(self, id):
        self._setId(id)
    def Title(self):
        return self.title
    def ZCTitle(self):
        return self.title
    def reindexObject(self):
        self.portal_catalog.reindexObject(self)

class SimpleCatalogTool(CatalogTool):
    def enumerateIndexes(self):
        return (
            ('Title', 'FieldIndex', None),
            ('ZCTitle', 'ZCTextIndex',
                 SimpleRecord(lexicon_id='cps_defaut_lexicon',
                              index_type='Okapi BM25 Rank')),
            )
    def enumerateColumns(self):
        return (
            'Title',
            )
    def enumerateLexicons(self):
        return (('cps_defaut_lexicon', # sic
                 Splitter(),
                 CaseNormalizer(),
                 StopWordRemover(),
                 ),
                )

class Upgrade335to336TestCase(unittest.TestCase):

    def _makeOne(self):
        self.root = Folder('')
        self.root.portal = Folder('portal')
        portal = self.root.portal
        portal.portal_catalog = SimpleCatalogTool()


    def test_upgrade(self):
        from Products.CPSCore.upgrade import upgrade_335_336_catalog_unicode
        self._makeOne()
        portal = self.root.portal
        catalog = portal.portal_catalog

        # Catalog old object with unicode title
        portal.workspaces = FakeObject('workspaces')
        workspaces = portal.workspaces
        workspaces.title = u"caf\xe9"
        catalog.indexObject(workspaces)

        # Even if we fix its title to str, we can't reindex it
        # because changing metadata has problems with current Zope.
        workspaces.title = "caf\xe9"
        # Note:
        # If the following test fails, it's because python has a
        # sys.getdefaultencoding() to something not 'ascii'.
        # Don't do that! Always use 'ascii'
        self.assertRaises(UnicodeDecodeError, workspaces.reindexObject)
        # (reset to buggy state to test upgrade later)
        workspaces.title = u"caf\xe9"

        # We can't insert any other object with latin1 title either
        obb = FakeObject('obb')
        obb.title = "ol\xe9"
        portal.obb = obb
        self.assertRaises(UnicodeDecodeError, catalog.indexObject, portal.obb)

        # Fixup the catalog
        res = upgrade_335_336_catalog_unicode(portal)
        self.assertEquals(res, "Cleaned up: 1 index entries, 1 metadata entries, "
                          "1 lexicon entries, 1 objects")

        # Check workspace title is fixed
        self.assertEquals(type(workspaces.title), str)
        # Check we can reindex fixed workspaces
        workspaces.reindexObject()
        # Check we can index non-unicode accents now
        catalog.indexObject(portal.obb)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(Upgrade335to336TestCase),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
