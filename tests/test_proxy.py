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
"""Tests for the proxies and the proxy tool.
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder

from Products.CPSCore.ProxyTool import ProxyTool
from Products.CPSCore.ProxyBase import ProxyBase, ProxyDocument

from dummy import DummyRepo, DummyPortalUrl, DummyWorkflowTool, DummyRoot


class PlacefulProxy(ProxyBase, Folder):

    def __init__(self, id, **kw):
        self.id = id
        ProxyBase.__init__(self, **kw)


def sortinfos(infos):
    tosort = [(i['rpath'], i) for i in infos]
    tosort.sort()
    return [t[1] for t in tosort]


class ProxyBaseTest(unittest.TestCase):

    def test_basic_api(self):
        proxy = ProxyBase()

        self.assertEquals(proxy.getDocid(), None)
        proxy.setDocid('bar')
        self.assertEquals(proxy.getDocid(), 'bar')

        self.assertEquals(proxy.getDefaultLanguage(), None)
        proxy.setDefaultLanguage('fr')
        self.assertEquals(proxy.getDefaultLanguage(), 'fr')

        lr = proxy._getLanguageRevisions()
        glr = proxy.getLanguageRevisions()
        self.assertEquals(lr, {})
        self.assertEquals(glr, {})
        # Check that dict was copied by getLanguageRevisions
        self.assert_(glr is not lr)

        proxy.setLanguageRevision('de', 3)
        self.assertEquals(proxy.getLanguageRevisions(), {'de': 3})
        proxy.setLanguageRevision('fr', 4)
        self.assertEquals(proxy.getLanguageRevisions(), {'fr': 4, 'de': 3})

        self.assertEquals(proxy.getFromLanguageRevisions(), {})
        flr = {'en': 55}
        proxy.setFromLanguageRevisions(flr)
        gflr = proxy.getFromLanguageRevisions()
        self.assertEquals(gflr, flr)
        # Check that dict was copied by getFromLanguageRevisions
        self.assert_(gflr is not flr)

        self.assertEquals(proxy.getTag(), None)
        proxy.setTag('tag')
        self.assertEquals(proxy.getTag(), 'tag')

        # Most other APIs just indirect to the proxy tool:
        # Can't test getLanguage, getRevision, getContent, getEditableContent,
        # proxyChanged, __getitem__, freezeProxy, _setSecurity,
        # _setSecurityRecursive, reindexObject, reindexObjectSecurity, Title,
        # title_or_id, SearchableText, Type, revertToRevisions without a
        # portal_proxies.

        # Can't test serializeProxy

    def test_proxy_presence(self):
        proxy = ProxyBase()
        self.assert_(proxy)

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

        proxy1 = ProxyBase(language_revs={'en': 78})
        proxy2 = ProxyBase(language_revs={'fr': 90})

        ptool._addProxy(proxy1, '123')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'en': 78}))])

        # Check that we can't add two proxies with same id
        self.assertRaises(ValueError, ptool._addProxy, proxy2, '123')
        # No side effects
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'en': 78}))])

        ptool._addProxy(proxy2, '456')
        items = ptool.listProxies()
        items.sort()
        self.assertEquals(items,
            [('123', (None, {'en': 78})), ('456', (None, {'fr': 90})),]
        )

        ptool._delProxy('456')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'en': 78}))])

        ptool._modifyProxy(proxy2, '123')
        self.assertEquals(ptool.listProxies(),
            [('123', (None, {'fr': 90}))])
        ptool._delProxy('123')
        self.assertEquals(len(ptool.listProxies()), 0)

    def testBestRevision(self):
        ptool = self.root.portal_proxies
        proxy = ProxyBase(language_revs={'fr': 33, 'en': 78})
        def absolute_url():
            return "fake path"
        proxy.absolute_url = absolute_url
        ptool._addProxy(proxy, '456')
        self.assertEquals(ptool.getBestRevision(proxy), ('en', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'en'), ('en', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'fr'), ('fr', 33))

    # XXX what about this?
        #self.assertEqual(ptool.getMatchedObject(123), 'ob_456_78')
        #self.assertEqual(ptool.getMatchedObject(123, 'en'), 'ob_456_78')
        #self.assertEqual(ptool.getMatchedObject(123, 'fr'), 'ob_456_33')

    def test_getProxyInfosFromDocid(self):
        ptool = self.root.portal_proxies
        proxy1 = PlacefulProxy('foo', docid='456',
                               language_revs={'fr': 33, 'en': 78})
        self.root.foo = proxy1
        proxy2 = PlacefulProxy('bar', docid='456',
                               language_revs={'fr': 33, 'en': 4})
        self.root.bar = proxy2
        ptool._addProxy(proxy1, '/foo')
        ptool._addProxy(proxy2, '/bar')
        infos = ptool.getProxyInfosFromDocid('456')
        infos = sortinfos(infos)
        self.assertEquals(infos,
            [{'visible': 1, 'rpath': '/bar', 'object': proxy2,
              'language_revs': {'fr': 33, 'en': 4}},
             {'visible': 1, 'rpath': '/foo', 'object': proxy1,
              'language_revs': {'fr': 33, 'en': 78}}])

        self.assertRaises(KeyError, ptool.getProxyInfosFromDocid, 'blah')


    def XXX_FIXME_testSecuritySynthesis(self):
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
