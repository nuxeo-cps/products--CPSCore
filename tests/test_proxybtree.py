# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""Tests for the btree proxies."""

import unittest
from Products.BTreeFolder2.BTreeFolder2 \
     import BTreeFolder2, ExhaustedUniqueIdsError
from OFS.ObjectManager import BadRequestException
from OFS.Folder import Folder
from Acquisition import aq_base
from Products.CPSCore.ProxyBase import ProxyBTreeFolder,\
     ProxyBTreeFolderishDocument

# Freebie tests
from Products.BTreeFolder2.tests.testBTreeFolder2 import \
     TrojanKey, BTreeFolder2Tests


class ProxyBTreeFolderTest(BTreeFolder2Tests):

    def setUp(self):
        self.f = ProxyBTreeFolder('root')
        ff = ProxyBTreeFolder('item')
        self.f._setOb(ff.id, ff)
        self.ff = self.f._getOb(ff.id)

    def testCheckId(self):
        self.assertEqual(self.f._checkId('xyz'), None)

    # skip base testWrapped test
    def testWrapped(self):
        pass


class ProxyBTreeFolderishDocumentTest(BTreeFolder2Tests):

    def setUp(self):
        self.f = ProxyBTreeFolderishDocument('root')
        ff = ProxyBTreeFolderishDocument('item')
        self.f._setOb(ff.id, ff)
        self.ff = self.f._getOb(ff.id)

    def testCheckId(self):
        self.assertEqual(self.f._checkId('xyz'), None)

    # skip base testWrapped test
    def testWrapped(self):
        pass


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(ProxyBTreeFolderTest),
        unittest.makeSuite(ProxyBTreeFolderishDocumentTest),
        ))

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
