# -*- coding: iso-8859-15 -*-
# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
# Author: Stéfane Fermigier <sf@nuxeo.com>
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
"""Tests for the CPSBaseDocument
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from OFS.Folder import Folder
from Products.CPSCore.CPSBase import CPSBaseDocument, CPSBase_adder


class CPSBaseDocumentTestCase(unittest.TestCase):

    def test1(self):
        doc = CPSBaseDocument(id='doc', title="The title")
        self.assertEquals(doc.getId(), 'doc')
        self.assertEquals(doc.Title(), "The title")

        doc.edit(title="A new title")
        self.assertEquals(doc.Title(), "A new title")
        self.assertEquals(doc.SearchableText().count("A new title"), 1)

        # Excercise path related to obscure unicode problem.
        latin1_title = "An unicode title áéïòû"
        unicode_title = unicode(latin1_title, "latin-1")
        doc.edit(title=unicode_title, description="üö")
        self.assertEquals(doc.Title(), unicode_title)
        self.assertEquals(
            doc.SearchableText().count(unicode_title), 1)


    def test2(self):
        folder = Folder('folder')
        doc = CPSBaseDocument(id='doc')
        CPSBase_adder(folder, doc)
        self.assert_('doc' in folder.objectIds())

def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(loader.loadTestsFromTestCase(CPSBaseDocumentTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
