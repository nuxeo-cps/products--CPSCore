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
from Testing.ZopeTestCase import doctest
from Products.CMFCore.tests.base.testcase import SecurityRequestTest
from Products.CMFCore.tests.base.testcase import LogInterceptor
from Products.CMFCore.tests.base.testcase import WarningInterceptor

import os
from zExceptions import BadRequest
from AccessControl import Unauthorized
from AccessControl import getSecurityManager
from AccessControl.PermissionRole import rolesForPermissionOn
from OFS.Image import File, Image
from OFS.SimpleItem import SimpleItem
from OFS.Folder import Folder

from Products.CPSCore.ProxyTool import ProxyTool
from Products.CPSCore.ProxyTool import DATAMODEL_PRESENT
from Products.CPSCore.ProxyBase import ProxyBase, ProxyFolder
from Products.CPSCore.ProxyBase import ProxyDocument, ProxyFolderishDocument
from Products.CPSCore.ProxyBase import ProxyBTreeFolder
from Products.CPSCore.ProxyBase import ProxyBTreeFolderishDocument
from Products.CPSCore.utils import KEYWORD_DOWNLOAD_FILE, KEYWORD_SIZED_IMAGE
from Products.CPSCore.utils import IMAGE_RESIZING_CACHE

from dummy import DummyPortalUrl
from dummy import DummyWorkflowTool
from dummy import DummyRoot
from dummy import DummyTypesTool
from dummy import DummyObjectRepositoryTool

from Products.CMFCore.permissions import View
from Products.CPSCore.permissions import ViewArchivedRevisions
ViewAR = ViewArchivedRevisions

TEST_DATA_PATH = os.path.join(os.path.split(__file__)[0], 'data')

class DummyProxyTool(Folder):

    # this is configurable, because some tests need objects to be
    # Folders (like CPSDocument are) but most of them should not
    # rely on that, not even to speak of ProxyBase itself (img caching is
    # an exception)
    ObClass = SimpleItem

    def __init__(self, ob_class=None):
        self.proxies = {}
        if ob_class is not None:
            self.ObClass = ob_class

    def _findRev(self, proxy, rev):
        if rev is not None:
            return rev
        lang = proxy.getDefaultLanguage()
        return proxy._getLanguageRevisions()[lang]

    def getContentByRevision(self, docid, rev):
        id = 'ob_%s_%s' % (docid, rev)
        if id not in self.objectIds():
            doc = self.ObClass(id)
            doc._setId(id)
            doc.portal_type = 'Some Type'
            self._setObject(id, doc)
        return self._getOb(id)

    def getContent(self, proxy, rev=None, **kw):
        docid = proxy.getDocid()
        rev = self._findRev(proxy, rev)
        return self.getContentByRevision(docid, rev)

    def freezeProxy(self, proxy):
        proxy.frozen = True

    def handleObjectEvent(self, ob, event):
        pass


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

    def test_security_freeze(self):
        docs = self.folder.docs
        docs.proxy1 = PlacefulProxy('proxy1', docid='d',
                                    default_language='en',
                                    language_revs={'en': 1, 'fr': 2})
        proxy1 = docs.proxy1

        # We can access freezeProxy
        try:
            proxy1.freezeProxy()
        except Unauthorized:
            self.fail("Catched Unauthorized exception")

        # it calls the proxy tool
        self.assert_(getattr(proxy1, 'frozen', False))

        # Unauthorized because it's TTW
        self.failUnlessRaises(Unauthorized, proxy1.freezeProxy,
                              REQUEST=self.app.REQUEST)


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

class ProxyThisTest(ZopeTestCase):
    """Tests the thisXXX methods of the proxies"""

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)
        self.root = DummyRoot()
        root = self.root
        root._setObject('folder', ProxyFolder('folder'))
        folder = root.folder
        folder._setObject('doc', ProxyDocument('doc'))
        folder._setObject('folderish', ProxyFolderishDocument('folderish'))
        folder._setObject('subfolder', ProxyBTreeFolder('subfolder'))

        folderish = folder.folderish
        folderish._setObject('subdoc', ProxyDocument('subdoc'))
        folderish._setObject('subfolderish', 
                             ProxyBTreeFolderishDocument('subfolderish'))
        subfolder = folder.subfolder
        subfolder._setObject('subfolderdoc', ProxyDocument('subfolderdoc'))

    def test_this(self):
        self.assert_(self.root.folder.thisProxyFolder().aq_base is 
                     self.root.folder.aq_base)
        self.assert_(self.root.folder.doc.thisProxyFolder().aq_base is 
                     self.root.folder.aq_base)
        self.assert_(self.root.folder.folderish.thisProxyFolder().aq_base is 
                     self.root.folder.aq_base)
        self.assert_(self.root.folder.folderish.subdoc.thisProxyFolder(
                     ).aq_base is self.root.folder.aq_base)
        self.assert_(self.root.folder.folderish.subfolderish.thisProxyFolder(
                     ).aq_base is self.root.folder.aq_base)

        self.assert_(self.root.folder.subfolder.thisProxyFolder().aq_base is 
                     self.root.folder.subfolder.aq_base)
        self.assert_(self.root.folder.subfolder.subfolderdoc.thisProxyFolder(
                     ).aq_base is self.root.folder.subfolder.aq_base)


class ProxyToolTest(ZopeTestCase, LogInterceptor):
    """Test CPS Proxy Tool."""

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)

        self.root = DummyRoot()
        root = self.root

        root._setObject('portal_repository', DummyObjectRepositoryTool())
        root._setObject('portal_proxies', ProxyTool())
        root._setObject('portal_url', DummyPortalUrl())
        root._setObject('portal_workflow', DummyWorkflowTool())
        root._setObject('portal_types', DummyTypesTool())

        root.docs = Folder()
        docs = root.docs
        docs.id = 'docs'

    def test_add_del_modify(self):
        ptool = self.root.portal_proxies
        self.assertEqual(ptool.listProxies(), [])

        proxy1 = ProxyBase(1357, language_revs={'en': 78})
        proxy2 = ProxyBase(1357, language_revs={'fr': 90})

        ptool._addProxy(proxy1, '/foo')
        self.assertEquals(ptool.listProxies(),
            [('/foo', (1357, {'en': 78}))])

        # We can re-add the same docid at the same path,
        # to be flexible about events sent.
        ptool._addProxy(proxy1, '/foo')

        # No side effects
        self.assertEquals(ptool.listProxies(),
            [('/foo', (1357, {'en': 78}))])

        ptool._addProxy(proxy2, '/bar')
        items = ptool.listProxies()
        items.sort()
        self.assertEquals(items, [('/bar', (1357, {'fr': 90})),
                                  ('/foo', (1357, {'en': 78}))])

        ptool._delProxy('/bar')
        self.assertEquals(ptool.listProxies(),
            [('/foo', (1357, {'en': 78}))])

        ptool._modifyProxy(proxy2, '/foo')
        self.assertEquals(ptool.listProxies(),
            [('/foo', (1357, {'fr': 90}))])
        ptool._delProxy('/foo')
        self.assertEquals(len(ptool.listProxies()), 0)

    def testBestRevision(self):
        ptool = self.root.portal_proxies
        proxy = ProxyBase(language_revs={'fr': 33, 'en': 78})
        def absolute_url():
            return "fake path"
        proxy.absolute_url = absolute_url
        ptool._addProxy(proxy, '/foo')
        self.assertEquals(ptool.getBestRevision(proxy), ('en', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'en'), ('en', 78))
        self.assertEquals(ptool.getBestRevision(proxy, 'fr'), ('fr', 33))

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

    def test_createRevision(self):
        # see #1608
        ptool = self.root.portal_proxies
        ptool.ignore_events = True # Dummy repotool cannot cope

        proxy = ProxyBase(1357, language_revs={'en': 78})

        # preparing the proxy to insulate what's being tested
        def getPortalTypeName():
            return 'Dummy Content'
        def dontReindex():
            pass
        proxy.getPortalTypeName = getPortalTypeName
        proxy.proxyChanged = dontReindex

        # call
        rev = ptool.createRevision(proxy, 'fr')

        if not DATAMODEL_PRESENT:
            return

        # datamodel was constructed and tied to the proxy
        passed = self.root.portal_repository._last_calls['createRevision']
        dm = passed['kw'].get('datamodel')
        self.assert_(dm is not None)
        self.assertEquals(dm.getProxy(), proxy)

        # previous datamodel stays the same, but is now tied to the proxy
        from Products.CPSCore.ProxyTool import DataModel
        dm = DataModel(None)
        rev = ptool.createRevision(proxy, 'fr2', datamodel=dm)
        passed = self.root.portal_repository._last_calls['createRevision']
        passed_dm = passed['kw'].get('datamodel')
        self.assert_(passed_dm is dm)
        self.assertEquals(dm.getProxy(), proxy)

class ProxyTraversalTest(ZopeTestCase):
    """Test the special traversal tokens."""

    def afterSetUp(self):
        ZopeTestCase.afterSetUp(self)
        self.root = DummyRoot()
        root = self.root

        self.folder._setObject('portal_proxies', DummyProxyTool(
            ob_class=Folder))
        ptool = self.folder.portal_proxies
        self.folder.proxies = Folder('proxies')

        # this relies on the dummy proxy tool behavior: getContent() creates
        # the actual content
        proxy = PlacefulProxy('proxy', docid=1, default_language='en',
                              language_revs=dict(en=1))
        self.folder.proxies._setObject('proxy', proxy)
        self.proxy = self.folder.proxies.proxy

    def test_file_downloader(self):
        proxy = self.proxy
        doc = proxy.getContent()
        # _setObject not availabale on doc (SimpleItem)
        doc.fobj = File('fobj', 'myfile.txt', 'File contents')

        # Starting traversal
        # TODO better to have something hihger level
        # (closer to what publisher would actually trigger)
        # we call utility methods that should never break at each stage
        # but don't check their outcome
        dl = proxy[KEYWORD_DOWNLOAD_FILE]
        s, r, u = str(dl), repr(dl), dl.absolute_url()
        dl.__bobo_traverse__(None, 'fobj')
        s, r, u = str(dl), repr(dl), dl.absolute_url()
        dl.__bobo_traverse__(None, 'hisfile.txt')
        s, r, u = str(dl), repr(dl), dl.absolute_url()

        self.assertEquals(dl.attrname, 'fobj')
        self.assertEquals(dl.file, doc.fobj)
        self.assertEquals(dl.filename, 'hisfile.txt')
        req = self.folder.REQUEST
        self.assertEquals(dl.index_html(req, req.RESPONSE), 'File contents')
        self.assertEquals(dl.content_type(), 'text/plain')

    def test_img_downloader_fullsize(self):
        proxy = self.proxy
        doc = proxy.getContent()
        doc._setObject('fobj', Image('fobj', 'myimg.png', 'File contents'))

        # Starting traversal
        # TODO better to have something hihger level
        # (closer to what publisher would actually trigger)
        # we call utility methods that should never break at each stage
        # but don't check their outcome
        dl = proxy[KEYWORD_SIZED_IMAGE]
        s, r, u = str(dl), repr(dl), dl.absolute_url()
        dl.__bobo_traverse__(None, 'fobj')
        s, r, u = str(dl), repr(dl), dl.absolute_url()
        dl.__bobo_traverse__(None, 'full')
        s, r, u = str(dl), repr(dl), dl.absolute_url()
        dl.__bobo_traverse__(None, 'hisimg.png')
        s, r, u = str(dl), repr(dl), dl.absolute_url()

        self.assertEquals(dl.attrname, 'fobj')
        self.assertEquals(dl.file, doc.fobj)
        self.assertEquals(dl.filename, 'hisimg.png')
        self.assertEquals(dl.additional, 'full')

        self.assertTrue(dl.isFullSize())
        dl.assertFullSize(meth_name='TEST')

        req = self.folder.REQUEST
        self.assertEquals(dl.index_html(req, req.RESPONSE), 'File contents')
        self.assertEquals(dl.content_type(), 'text/plain')

    def test_img_downloader_fullspec(self):
        proxy = self.proxy
        doc = proxy.getContent()
        f = open(os.path.join(TEST_DATA_PATH, 'logo_cps.png'))
        doc._setObject('fobj', Image('fobj', 'myimg.png', f))

        dl = proxy[KEYWORD_SIZED_IMAGE]
        dl.__bobo_traverse__(None, 'fobj')
        dl.__bobo_traverse__(None, '320x200')
        dl.__bobo_traverse__(None, 'hisimg.png')

        self.assertFalse(dl.isFullSize())
        self.assertRaises(BadRequest, dl.assertFullSize, meth_name='TEST')

        req = self.folder.REQUEST
        img_content = dl.index_html(req, req.RESPONSE)
        self.assertEquals(dl.content_type(), 'image/png')

    def test_img_downloader_largest(self):
        proxy = self.proxy
        doc = proxy.getContent()
        f = open(os.path.join(TEST_DATA_PATH, 'logo_cps.png'))
        doc._setObject('fobj', Image('fobj', 'myimg.png', f))

        dl = proxy[KEYWORD_SIZED_IMAGE]
        dl.__bobo_traverse__(None, 'fobj')
        dl.__bobo_traverse__(None, 'l320')
        dl.__bobo_traverse__(None, 'hisimg.png')

        self.assertFalse(dl.isFullSize())
        self.assertEquals(dl.targetGeometry(), (320, 98))
        self.assertRaises(BadRequest, dl.assertFullSize, meth_name='TEST')

        req = self.folder.REQUEST
        img_content = dl.index_html(req, req.RESPONSE)
        self.assertEquals(dl.content_type(), 'image/png')

    def test_img_downloader_width(self):
        proxy = self.proxy
        doc = proxy.getContent()
        f = open(os.path.join(TEST_DATA_PATH, 'logo_cps.png'))
        doc._setObject('fobj', Image('fobj', 'myimg.png', f))

        dl = proxy[KEYWORD_SIZED_IMAGE]
        dl.__bobo_traverse__(None, 'fobj')
        dl.__bobo_traverse__(None, 'w320')
        dl.__bobo_traverse__(None, 'hisimg.png')

        self.assertFalse(dl.isFullSize())
        self.assertEquals(dl.targetGeometry(), (320, 98))
        self.assertRaises(BadRequest, dl.assertFullSize, meth_name='TEST')

        req = self.folder.REQUEST
        img_content = dl.index_html(req, req.RESPONSE)
        self.assertEquals(dl.content_type(), 'image/png')

    def test_img_downloader_height(self):
        proxy = self.proxy
        doc = proxy.getContent()
        f = open(os.path.join(TEST_DATA_PATH, 'logo_cps.png'))
        doc._setObject('fobj', Image('fobj', 'myimg.png', f))

        dl = proxy[KEYWORD_SIZED_IMAGE]
        dl.__bobo_traverse__(None, 'fobj')
        dl.__bobo_traverse__(None, 'h130')
        dl.__bobo_traverse__(None, 'hisimg.png')

        self.assertFalse(dl.isFullSize())
        self.assertEquals(dl.targetGeometry(), (425, 130))
        self.assertRaises(BadRequest, dl.assertFullSize, meth_name='TEST')

        req = self.folder.REQUEST
        img_content = dl.index_html(req, req.RESPONSE)
        self.assertEquals(dl.content_type(), 'image/png')

def test_suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTest(doctest.DocTestSuite('Products.CPSCore.ProxyBase'))
    suite.addTest(loader.loadTestsFromTestCase(ProxyBaseTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyFolderTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyToolTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyThisTest))
    suite.addTest(loader.loadTestsFromTestCase(ProxyTraversalTest))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
