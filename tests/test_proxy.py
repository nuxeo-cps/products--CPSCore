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

from Products.CPSCore.ProxyTool import ProxyTool
from Products.CPSCore.ProxyBase import ProxyBase, ProxyDocument
from Products.CPSCore.ObjectRepositoryTool import ObjectRepositoryTool

from dummy import DummyRepo, DummyPortalUrl, DummyWorkflowTool, DummyRoot


class ProxyBaseTest(unittest.TestCase):

    def test1(self):
        proxy = ProxyBase()

        self.assertEquals(proxy.getDocid(), None)

        proxy.setDocid('bar')
        self.assertEquals(proxy.getDocid(), 'bar')

        self.assertEquals(proxy.getDefaultLanguage(), None)

        proxy.setDefaultLanguage('fr')
        self.assertEquals(proxy.getDefaultLanguage(), 'fr')

        self.assertEquals(proxy.getLanguageRevisions(), {})
        self.assertEquals(proxy._getLanguageRevisions(), {})
        self.assert_(
            proxy.getLanguageRevisions() is not proxy._getLanguageRevisions())

        proxy.setLanguageRevision('de', 3)
        self.assertEquals(proxy.getLanguageRevisions(), 
            {'de': 3})
        proxy.setLanguageRevision('fr', 4)
        self.assertEquals(proxy.getLanguageRevisions(), 
            {'fr': 4, 'de': 3})

        self.assertEquals(proxy.getFromLanguageRevisions(), {})
        # XXX what are FromLanguageRevisions anyway ?

        self.assertEquals(proxy.getTag(), None)
        proxy.setTag('tag')
        self.assertEquals(proxy.getTag(), 'tag')

        # Can't test getLanguage, getRevision, getContent, getEditableContent,
        # proxyChanged, __getitem__, freezeProxy, _setSecurity,
        # _setSecurityRecursive, reindexObject, reindexObjectSecurity, Title,
        # title_or_id, SearchableText, Type, revertToRevisions without a
        # portal_proxies.

        # Can't test serializeProxy


class ProxyToolTest(SecurityRequestTest):
    """Test CPS Proxy Tool."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = DummyRoot()
        root = self.root

        root._setObject('portal_proxies', ProxyTool())
        root._setObject('portal_repository', DummyRepo())
        root._setObject('portal_url', DummyPortalUrl())
        root._setObject('portal_workflow', DummyWorkflowTool())

        root.docs = Folder()
        docs = root.docs
        docs.id = 'docs'

    def test_add_del_modify(self):
        ptool = self.root.portal_proxies
        self.assertEqual(ptool.listProxies(), [])

        proxy1 = ProxyBase(language_revs={'*': 78})
        proxy2 = ProxyBase(language_revs={'*': 90})

        ptool._addProxy(proxy1, '123')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'*': 78}))])

        # Check that we can't add two proxies with same id
        self.assertRaises(ValueError, ptool._addProxy, proxy2, '123')
        # No side effects
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'*': 78}))])

        ptool._addProxy(proxy2, '456')
        items = ptool.listProxies()
        items.sort()
        self.assertEquals(items,
            [('123', (None, {'*': 78})), ('456', (None, {'*': 90})),]
        )

        ptool._delProxy('456')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'*': 78}))])

        ptool._modifyProxy(proxy2, '123')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'*': 90}))])
        ptool._delProxy('123')
        self.assertEquals(len(ptool.listProxies()), 0)

    def testBestRevision(self):
        ptool = self.root.portal_proxies
        proxy = ProxyBase(language_revs={'fr': 33, '*': 78})
        ptool._addProxy(proxy, '456')
        self.assertEquals(ptool.getBestRevision(proxy), ('*', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'en'), ('*', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'fr'), ('fr', 33))

    # XXX what about this?
        #self.assertEqual(ptool.getMatchedObject(123), 'ob_456_78')
        #self.assertEqual(ptool.getMatchedObject(123, 'en'), 'ob_456_78')
        #self.assertEqual(ptool.getMatchedObject(123, 'fr'), 'ob_456_33')

    # XXX: This tests a now defunct method (getMatchingProxies). 
    # What should we test instead ?
    def _test_getMatchingProxies(self):
        ptool = self.root.portal_proxies
        proxy1 = ProxyBase(language_revs={'fr': 33, '*': 78})
        proxy2 = ProxyBase(language_revs={'fr': 33, 'en': 0})
        proxy3 = ProxyBase(language_revs={'fr': 78, 'en': 78})
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


    def testSecuritySynthesis(self):
        root = self.root
        ptool = root.portal_proxies
        repo = root.portal_repository
        docs = root.docs

        proxy1 = ProxyDocument('proxy1',
                               docid='d', language_revs={'en': 1, 'fr': 2})
        proxy2 = ProxyDocument('proxy2',
                               docid='d', language_revs={'en': 3, 'fr': 2})
        proxy3 = ProxyDocument('proxy3',
                               docid='d', language_revs={'en': 3})
        docs.proxy1 = proxy1
        docs.proxy2 = proxy2
        docs.proxy3 = proxy3
        proxy1 = docs.proxy1
        proxy2 = docs.proxy2
        proxy3 = docs.proxy3
        ptool._addProxy(proxy1, 'docs/proxy1')
        ptool._addProxy(proxy2, 'docs/proxy2')
        ptool._addProxy(proxy3, 'docs/proxy3')

        l = ptool.listProxies()
        l.sort()
        self.assertEquals(l, [('docs/proxy1', ('d', {'en': 1, 'fr': 2})),
                              ('docs/proxy2', ('d', {'en': 3, 'fr': 2})),
                              ('docs/proxy3', ('d', {'en': 3})),
                              ])

        repo._testClearSecurity()

        proxy1.manage_permission('View', ['Reviewer'])
        proxy1.manage_setLocalRoles('foo', ['Reviewer'])
        ptool.setSecurity(proxy1)
        self.assertEquals(repo._testGetSecurity(),
                          {'d.1': {'foo': ['View']},
                           'd.2': {'foo': ['View']}})

        proxy2.manage_permission('Modify', ['Reader'])
        proxy2.manage_setLocalRoles('bar', ['Reader'])
        ptool.setSecurity(proxy2)
        self.assertEquals(repo._testGetSecurity(),
                          {'d.1': {'foo': ['View']},
                           'd.2': {'foo': ['View'], 'bar': ['Modify']},
                           'd.3': {'bar': ['Modify']}})

        proxy3.manage_permission('DoStuff', ['Reviewer'])
        proxy3.manage_setLocalRoles('foo', ['Reviewer'])
        ptool.setSecurity(proxy3)
        self.assertEquals(repo._testGetSecurity(),
                          {'d.1': {'foo': ['View']},
                           'd.2': {'foo': ['View'], 'bar': ['Modify']},
                           'd.3': {'foo': ['DoStuff'], 'bar': ['Modify']}})

        proxy2.manage_permission('Modify', [])
        proxy2.manage_setLocalRoles('bar', ['Reader'])
        ptool.setSecurity(proxy2)
        self.assertEquals(repo._testGetSecurity(),
                          {'d.1': {'foo': ['View']},
                           'd.2': {'foo': ['View']},
                           'd.3': {'foo': ['DoStuff']}})

        proxy1.manage_permission('Modify', ['Reviewer'])
        ptool.setSecurity(proxy1)
        self.assertEquals(repo._testGetSecurity(),
                          {'d.1': {'foo': ['View', 'Modify']},
                           'd.2': {'foo': ['View', 'Modify']},
                           'd.3': {'foo': ['DoStuff']}})


def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(loader.loadTestsFromTestCase(ProxyBaseTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyToolTest))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
