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
"""Tests for the proxies and the proxy tool.
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem

from Products.CPSCore.ProxyTool import ProxyTool
from Products.CPSCore.ProxyBase import ProxyBase

class DummyRepo(SimpleItem):
    def getObjectVersion(self, repoid, version_info):
        return 'ob_%s_%s' % (repoid, version_info)


class ProxyToolTests(SecurityRequestTest):
    """Test CPS Proxy Tool."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = Folder()
        self.root.id = 'root'
        root = self.root

        ptool = ProxyTool()
        root._setObject('portal_proxies', ptool)


    #def tearDown( self ):
    #    SecurityRequestTest.tearDown(self)

    ##########

    def test_add_del_modify(self):
        ptool = self.root.portal_proxies
        self.assertEqual(tuple(ptool.listProxies()), ())

        proxy1 = ProxyBase(language_revs={'*': 78})
        proxy2 = ProxyBase(language_revs={'*': 90})

        ptool._addProxy(proxy1, '123')
        self.assertEquals(tuple(ptool.listProxies()),
            (('123', (None, {'*': 78})),))

        self.assertRaises(ValueError, ptool._addProxy, proxy2, '123')
        self.assertEquals(tuple(ptool.listProxies()),
            (('123', (None, {'*': 78})),))

        ptool._addProxy(proxy2, '456')
        items = ptool.listProxies()
        items.sort()
        self.assertEquals(tuple(items),
            (('123', (None, {'*': 78})),
             ('456', (None, {'*': 90})),)
        )

        ptool._delProxy('456')
        self.assertEquals(tuple(ptool.listProxies()),
            (('123', (None, {'*': 78})),))

        #ptool.modifyProxy(, '444', {'en': 1})
        #self.assertEqual(tuple(ptool.listProxies()),
        #                 ((222, ('444', {'en': 1})),))
        #ptool.delProxy(222)
        #self.assertEqual(tuple(ptool.listProxies()), ())


    def test_getMatchedObject(self):
        self.root._setObject('portal_repository', DummyRepo())
        ptool = self.root.portal_proxies
        ptool.addProxy(123, '456', {'fr': 33, '*': 78})
        self.assertEqual(ptool.getMatchedObject(123), 'ob_456_78')
        self.assertEqual(ptool.getMatchedObject(123, 'en'), 'ob_456_78')
        self.assertEqual(ptool.getMatchedObject(123, 'fr'), 'ob_456_33')

    def test_getMatchingProxies(self):
        self.root._setObject('portal_repository', DummyRepo())
        ptool = self.root.portal_proxies
        ptool.addProxy(123, '456', {'fr': 33, '*': 78})
        ptool.addProxy(444, '456', {'*': 33, 'en': 0})
        ptool.addProxy(888, '456', {'fr': 78, 'en': 78})
        infos = ptool.getMatchingProxies('456', 33)
        self.assertEqual(infos, {123: ['fr'], 444: ['*']})
        infos = ptool.getMatchingProxies('456', 78)
        self.failUnless(infos.has_key(888))
        infos[888].sort()
        self.assertEqual(infos, {123: ['*'], 888: ['en', 'fr']})
        infos = ptool.getMatchingProxies('456', 314)
        self.assertEqual(infos, {})
        infos = ptool.getMatchingProxies('nosuch', 22)
        self.assertEqual(infos, {})


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(ProxyToolTests)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
