# -*- coding: iso-8859-15 -*-
# Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""Tests Indexing through the catalog.
"""

import random
import unittest
from Testing import ZopeTestCase
from Testing.ZopeTestCase import PortalTestCase

# Ensure we have made our patches
ZopeTestCase.installProduct('CPSCompat')
# Need patches for groups too
ZopeTestCase.installProduct('CPSUserFolder')
# We need the FTIs for proxies
ZopeTestCase.installProduct('CPSCore')

ZopeTestCase.installProduct('ZCTextIndex')


from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem
from Products.CPSCore.IndexationManager import get_indexation_manager
from Products.CPSCore.EventServiceTool import getEventService


def catalog_paths(catalog):
    paths = list(catalog._catalog.uids.keys())
    paths.sort()
    return paths


class DummyRoot(Folder):
    def getPhysicalRoot(self):
        return self

from Products.CMFCore.CMFCatalogAware import CMFCatalogAware
class DummyOb(SimpleItem, CMFCatalogAware):
    title = 'default title'
    def __init__(self, id):
        self._setId(id)
    def _setPortalTypeName(self, portal_type):
        self.portal_type = portal_type
    def Title(self):
        return self.title
    def Type(self):
        return 'the type'
    def setLanguage(self, language):
        self.language = language
    def Language(self):
        return self.language

class FakeTI:
    _isTypeInformation = True
    def _constructInstance(self, container, id, **kw):
        ob = DummyOb(id)
        container._setObject(id, ob)
        return container._getOb(id)
    def getIcon(self):
        return 'icon.gif'

from Products.CMFCore.CatalogTool import CatalogTool
class CPSCatalogTool(CatalogTool):
    def enumerateIndexes(self):
        return CatalogTool.enumerateIndexes(self) + (
            ('localUsersWithRoles', 'KeywordIndex', None),
            ('Language', 'FieldIndex', None),
            )


class IndexingTest(PortalTestCase):

    def getPortal(self):
        self.app.portal = Folder('portal')
        return self.app.portal

    def _setupHomeFolder(self):
        pass

    def afterSetUp(self):
        self.portal._setObject('portal_catalog', CPSCatalogTool())
        self.portal.dummy = DummyOb('dummy')

    def test_cmf_security_indexes(self):
        ok = ('allowedRolesAndUsers', 'localUsersWithRoles')
        self.assertEquals(self.portal.dummy._cmf_security_indexes, ok)

    def test_reindex_security_indexes(self):
        # Check that our specific security-related index is reindexed by
        # reindexObjectSecurity.
        dummy = self.portal.dummy
        cat = self.portal.portal_catalog

        dummy.indexObject()
        res = cat.unrestrictedSearchResults()
        self.assertEquals(len(res), 1)
        res = cat.unrestrictedSearchResults(localUsersWithRoles='user:bob')
        self.assertEquals(len(res), 0)

        # Now add a local role
        dummy.manage_setLocalRoles('bob', ['Winner'])
        dummy.reindexObjectSecurity()
        res = cat.unrestrictedSearchResults(localUsersWithRoles='user:bob')
        self.assertEquals(len(res), 1)


class ProxyIndexingTest(PortalTestCase):

    def setUp(self):
        from Products.CPSCore.tests.setup import fullFiveSetup
        fullFiveSetup()
        PortalTestCase.setUp(self)

    def getPortal(self):
        self.app.portal = Folder('portal')
        return self.app.portal

    def _setup(self):
        self._setupUserFolder()
        self._setupUser()
        self.login()
        self._setupTools()
        get_indexation_manager().setSynchronous(True)

    def _setupTools(self):
        from Products.CPSCore.URLTool import URLTool
        from Products.CPSCore.ProxyTool import ProxyTool
        from Products.CPSCore.ObjectRepositoryTool import ObjectRepositoryTool
        from Products.CPSCore.EventServiceTool import EventServiceTool
        from Products.CMFCore.TypesTool import TypesTool

        portal = self.portal
        portal._setObject('portal_url', URLTool())
        portal._setObject('portal_proxies', ProxyTool())
        portal._setObject('portal_repository', ObjectRepositoryTool())

        portal._setObject('portal_eventservice', EventServiceTool())
        evtool = portal.portal_eventservice
        evtool.manage_addSubscriber(subscriber='portal_proxies',
                                    action='proxy',
                                    meta_type='*',
                                    event_type='*',
                                    notification_type='synchronous')

        portal._setObject('portal_types', TypesTool())
        ttool = portal.portal_types
        ttool.Dummy = FakeTI()

        portal._setObject('portal_catalog', CPSCatalogTool())

    def test_proxy_indexing(self):
        catalog = self.portal.portal_catalog
        pxtool = self.portal.portal_proxies
        container = self.portal
        proxy = pxtool.createEmptyProxy('document', container, 'Dummy', 'foo')
        proxy.setDefaultLanguage('fr')
        pxtool.createRevision(proxy, 'fr')
        brain = catalog.searchResults()[0]
        self.assertEquals(brain.Title, 'default title')

        # Change the title, reindex the proxy
        docfr = proxy.getContent()
        docfr.title = 'iceberg detected'
        proxy.reindexObject()
        brain = catalog.searchResults()[0]
        self.assertEquals(brain.Title, 'iceberg detected')

        # Change the title, reindex the doc
        docfr.title = 'titanic skins'
        docfr.reindexObject() # not enough
        brain = catalog.searchResults()[0]
        self.assertEquals(brain.Title, 'iceberg detected')
        # Now send a notification, proxy tool will act on it
        evtool = getEventService(self.portal)
        evtool.notify('sys_modify_object', docfr, {})
        brain = catalog.searchResults()[0]
        self.assertEquals(brain.Title, 'titanic skins')

    def show_cat_paths(self):
        catalog = self.portal.portal_catalog
        for comp, iotree in catalog._catalog.indexes['path']._index.items():
            print '  ', comp
            for level, set in iotree.items():
                print '   ', level, ':', list(set.keys())

    def test_proxy_languages(self):
        catalog = self.portal.portal_catalog
        pxtool = self.portal.portal_proxies
        container = self.portal
        proxy = pxtool.createEmptyProxy('document', container, 'Dummy', 'foo')
        proxy.setDefaultLanguage('fr')

        # --- Create first language
        pxtool.createRevision(proxy, 'fr')
        self.assertEquals(catalog_paths(catalog), [
            '/portal/foo',
            ])
        docfr = proxy.getContent()
        self.assertEquals(docfr.language, 'fr')

        # --- Add another language
        proxy.addLanguageToProxy('it')
        self.assertEquals(catalog_paths(catalog), [
            '/portal/foo/viewLanguage/fr',
            '/portal/foo/viewLanguage/it',
            ])
        docfr = proxy.getContent(lang='fr')
        self.assertEquals(docfr.language, 'fr')
        docit = proxy.getContent(lang='it')
        self.assertEquals(docit.language, 'it')

        # Check path index works with viewLanguage
        brains = catalog.unrestrictedSearchResults(
            path='/portal/foo/viewLanguage')
        self.assertEquals(len(brains), 2)

        # Check reindexing
        docit.title = 'aliens land'
        proxy.reindexObject()
        brain = catalog.searchResults(Language='it')[0]
        self.assertEquals(brain.Title, 'aliens land')

        # Reindex at lower level using path
        # (what refreshCatalog or reindexObjectSecurity do)
        # Check that we only reindex what's asked
        docfr.title = 'napoleon dies'
        docit.title = 'cicciolina elected'
        catalog.catalog_object(proxy, '/portal/foo/viewLanguage/fr')
        brain = catalog.searchResults(Language='fr')[0]
        self.assertEquals(brain.Title, 'napoleon dies')
        brain = catalog.searchResults(Language='it')[0]
        self.assertEquals(brain.Title, 'aliens land') # not yet updated

        # --- Delete a language
        self.assertRaises(ValueError, proxy.delLanguageFromProxy, 'fr')
        proxy.delLanguageFromProxy('it')
        self.assertEquals(catalog_paths(catalog), [
            '/portal/foo',
            ])

        # XXX check unindexObject

class IndexableObjectWrapperTestCase(ZopeTestCase.PortalTestCase):

    def _setup(self):
        self._setupUserFolder()
        self._setupUser()
        self.login()
        get_indexation_manager().setSynchronous(True)

    def getPortal(self):
        self.app.portal = Folder( 'portal')
        return self.app.portal

    def test_btree_position_in_container(self):

        from Products.CMFCore.CMFBTreeFolder import CMFBTreeFolder
        from Acquisition import aq_inner, aq_parent
        
        self.app.portal._setObject('btree', CMFBTreeFolder('btree'))
        btree = getattr(self.app.portal, 'btree')
        btree._setObject('item', SimpleItem('item'))
        item = getattr(btree, 'item')

        self.assertEqual(aq_parent(aq_inner(item)), btree)
        from Products.CPSCore.PatchCMFCoreCatalogTool import \
             IndexableObjectWrapper

        wrapper = IndexableObjectWrapper({}, item)
        self.assertEqual(0, wrapper.position_in_container())

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(IndexingTest),
        unittest.makeSuite(ProxyIndexingTest),
        unittest.makeSuite(IndexableObjectWrapperTestCase),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
