# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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
"""Tests for the Indexation Manager
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from Acquisition import aq_parent, aq_inner, aq_base
from OFS.Folder import Folder

from dummy import Dummy

from Products.CPSCore.TransactionCommitSubscribers import IndexationManager

class IndexationManagerTest(unittest.TestCase):

    def test_fixtures(self):
        self.assertEqual(IndexationManager._transaction_done, True)
        self.assertEqual(IndexationManager._queue, [])

    def test_registration(self):
        IndexationManager.register()
        self.assertEqual(IndexationManager._transaction_done, False)
        self.assertEqual(IndexationManager._queue, [])
    
        # Register Dummy
        dummy = Dummy('dummy')
    
        IndexationManager.push(dummy)
        self.assert_(dummy in IndexationManager._getObjectsInQueue())
        self.assert_(len(IndexationManager._queue) == 1)
    
        # Try to register dummy twice but no way
        IndexationManager.push(dummy)
        self.assert_(dummy in IndexationManager._getObjectsInQueue())
        self.assert_(len(IndexationManager._queue) == 1)
    
    def test_transaction(self):
        get_transaction().begin()
        IndexationManager.register()
    
        # Schedule dummy
        dummy = Dummy('dummy')
    
        IndexationManager.push(dummy)
        get_transaction().commit()
    
        # Test the reinit
        self.test_fixtures()
    
    def test_transaction_aborting(self):
        get_transaction().begin()
        IndexationManager.register()
    
        # Schedule dummy
        dummy = Dummy('dummy')
    
        IndexationManager.push(dummy)
    
        # Abort
        get_transaction().abort()
    
        # test the reinit
        self.test_fixtures()
        
def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(loader.loadTestsFromTestCase(IndexationManagerTest))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
