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


class ProxyBTreeFolderTest(unittest.TestCase):

    def setUp(self):
        from Products.CPSCore.ProxyBase import ProxyBTreeFolder
        self.f = ProxyBTreeFolder('root')

    def testCheckId(self):
        self.assertEquals(self.f._checkId('xyz'), None)

    def testTrue(self):
        # Test true even if empty
        self.assertEquals(bool(self.f), True)


class ProxyBTreeFolderishDocumentTest(unittest.TestCase):

    def setUp(self):
        from Products.CPSCore.ProxyBase import ProxyBTreeFolderishDocument
        self.f = ProxyBTreeFolderishDocument('root')

    def testCheckId(self):
        self.assertEquals(self.f._checkId('xyz'), None)

    def testTrue(self):
        # Test true even if empty
        self.assertEquals(bool(self.f), True)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(ProxyBTreeFolderTest),
        unittest.makeSuite(ProxyBTreeFolderishDocumentTest),
        ))

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
