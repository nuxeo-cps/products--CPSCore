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

import unittest
from Testing.ZopeTestCase import ZopeTestCase
from Products.CMFCore.tests.base.testcase import SecurityRequestTest
from Products.CMFCore.tests.base.testcase import LogInterceptor
from Products.CMFCore.tests.base.testcase import WarningInterceptor

from AccessControl import Unauthorized
from AccessControl import getSecurityManager
from AccessControl.PermissionRole import rolesForPermissionOn
from OFS.SimpleItem import SimpleItem
from OFS.Folder import Folder

from Products.CPSCore.ProxyTool import ProxyTool
from Products.CPSCore.ProxyBase import ProxyBase, ProxyFolder

from dummy import DummyPortalUrl, DummyWorkflowTool, DummyRoot

from Products.CMFCore.permissions import View
from Products.CPSCore.permissions import ViewArchivedRevisions
ViewAR = ViewArchivedRevisions


class DummyProxyTool(Folder):
    def __init__(self):
        self.proxies = {}

    def _findRev(self, proxy, rev):
        if rev is not None:
            return rev
        lang = proxy.getDefaultLanguage()
        return proxy._getLanguageRevisions()[lang]

    def getContentByRevision(self, docid, rev):
        id = 'ob_%s_%s' % (docid, rev)
        if id not in self.objectIds():
            doc = SimpleItem(id)
            doc._setId(id)
            doc.portal_type = 'Some Type'
            self._setObject(id, doc)
        return self._getOb(id)

    def getContent(self, proxy, rev=None, **kw):
        docid = proxy.getDocid()
        rev = self._findRev(proxy, rev)
        return self.getContentByRevision(docid, rev)

class PlacefulProxy(ProxyBase, Folder):
    def __init__(self, id, **kw):
        self.id = id
        ProxyBase.__init__(self, **kw)


def sortinfos(infos):
    tosort = [(i['rpath'], i) for i in infos]
    tosort.sort()
    return [t[1] for t in tosort]


class ProxyBaseTest(ZopeTestCase):

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)
        # Use the ZopeTestCase folder as root, as we need to have
        # acl_user in context.
        self.folder._setObject('portal_proxies', DummyProxyTool())
        self.folder.docs = Folder('docs')

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
        # FIXME: add tests for those.
        # Can't test getLanguage, getRevision, getContent, getEditableContent,
        # proxyChanged, __getitem__, freezeProxy
        # reindexObject, reindexObjectSecurity, Title,
        # title_or_id, SearchableText, Type, revertToRevisions without a
        # portal_proxies.

        # Can't test serializeProxy

    def test_proxy_presence(self):
        proxy = ProxyBase()
        self.assert_(proxy)

    def test_security(self):
        pxtool = self.folder.portal_proxies
        docs = self.folder.docs
        user = getSecurityManager().getUser()
        docs.proxy1 = PlacefulProxy('proxy1', docid='d',
                                    default_language='en',
                                    language_revs={'en': 1, 'fr': 2})
        proxy1 = docs.proxy1
        doc = proxy1.getContent()
        self.assertEquals(doc.getId(), 'ob_d_1')

        proxy1.manage_permission(View, ['Winner'])
        self.assert_('Winner' in rolesForPermissionOn(View, proxy1))
        self.assert_('Winner' in rolesForPermissionOn(View, doc))
        self.failIf(user.has_role('Winner', proxy1))
        self.failIf(user.has_role('Winner', doc))

        proxy1.manage_setLocalRoles('test_user_1_', ['Winner'])
        self.assert_('Winner' in rolesForPermissionOn(View, proxy1))
        self.assert_('Winner' in rolesForPermissionOn(View, doc))
        self.assert_(user.has_role('Winner', proxy1))
        self.assert_(user.has_role('Winner', doc))

    def test_security_archive(self):
        pxtool = self.folder.portal_proxies
        docs = self.folder.docs
        user = getSecurityManager().getUser()
        docs.proxy1 = PlacefulProxy('proxy1', docid='d',
                                    default_language='en',
                                    language_revs={'en': 1, 'fr': 2})
        proxy1 = docs.proxy1
        self.assertEquals('/'.join(proxy1.getPhysicalPath()),
                          '/test_folder_1_/docs/proxy1')

        # Without permission, no access to archive
        proxy1.manage_permission(View, ['Winner'])
        proxy1.manage_permission(ViewAR, ['Winner'])
        self.assert_('Winner' in rolesForPermissionOn(View, proxy1))
        self.assert_('Winner' in rolesForPermissionOn(ViewAR, proxy1))
        self.failIf(user.has_role('Winner', proxy1))
        self.assertRaises(Unauthorized, proxy1.restrictedTraverse,
                          'archivedRevision/2')

        # With appropriate permission, get the archive
        proxy1.manage_setLocalRoles('test_user_1_', ['Winner'])
        self.assert_('Winner' in rolesForPermissionOn(View, proxy1))
        self.assert_('Winner' in rolesForPermissionOn(ViewAR, proxy1))
        self.assert_(user.has_role('Winner', proxy1))
        arch = proxy1.restrictedTraverse('archivedRevision/2')
        self.assert_('Winner' in rolesForPermissionOn(View, arch))
        self.assert_(user.has_role('Winner', arch))
        self.assertEquals('/'.join(arch.getPhysicalPath()),
                          '/test_folder_1_/docs/proxy1/archivedRevision/2')
        # The archive can be dereferenced like a normal proxy
        doc = arch.getContent()
        self.assertEquals(doc.getId(), 'ob_d_2')
        self.assert_('Winner' in rolesForPermissionOn(View, doc))
        self.assert_(user.has_role('Winner', doc))

class ProxyFolderTest(ZopeTestCase, WarningInterceptor):

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)
        # Use the ZopeTestCase folder as root, as we need to have
        # acl_user in context.
        self.folder._setObject('portal_proxies', DummyProxyTool())
        self.folder.docs = Folder('docs')

    def testOrdering(self):
        # Proxy Folders should have ordering support
        self.folder._setObject('proxyfolder', ProxyFolder('proxyfolder'))
        pxfolder = self.folder.proxyfolder
        pxfolder._setObject('object1', PlacefulProxy('object1'))
        pxfolder._setObject('object2', PlacefulProxy('object2'))
        pxfolder._setObject('object3', PlacefulProxy('object3'))
        # Check the order:
        ids = self.folder.proxyfolder.objectIds()
        self.assertEqual(ids, ['object1', 'object2', 'object3'])
        # Move
        pxfolder.moveObjectsUp( ('object2', 'object3') )
        ids = self.folder.proxyfolder.objectIds()
        self.assertEqual(ids, ['object2', 'object3', 'object1'])
        # BBB We still need support for old names of the methods:
        self._trap_warning_output()
        pxfolder.move_object_up('object3')
        self.assert_(self._our_stderr_stream.getvalue())
        self._free_warning_output()
        ids = self.folder.proxyfolder.objectIds()
        self.assertEqual(ids, ['object3', 'object2', 'object1'])

class ProxyToolTest(ZopeTestCase, LogInterceptor):
    """Test CPS Proxy Tool."""

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)

        self.root = DummyRoot()
        root = self.root

        root._setObject('portal_proxies', ProxyTool())
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
        from zLOG import ERROR
        self._catch_log_errors(ERROR)
        self.logged = None
        self.assertRaises(ValueError, ptool._addProxy, proxy2, '123')
        self.assert_(self.logged)
        self._ignore_log_errors()

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
        # XXX check 'visible' values, using a proper user folder
        # in the acquisition context.
        self.assertEquals(infos,
            [{'visible': None, 'rpath': '/bar', 'object': proxy2,
              'language_revs': {'fr': 33, 'en': 4}},
             {'visible': None, 'rpath': '/foo', 'object': proxy1,
              'language_revs': {'fr': 33, 'en': 78}}])

        self.assertRaises(KeyError, ptool.getProxyInfosFromDocid, 'blah')


def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(loader.loadTestsFromTestCase(ProxyBaseTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyFolderTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyToolTest))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
