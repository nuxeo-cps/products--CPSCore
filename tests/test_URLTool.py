# (C) Copyright 2003-2008 Nuxeo SAS <http://nuxeo.com>
# Authors:
# Stefane Fermigier <sf@nuxeo.com>
# M.-A. Darche <madarche@nuxeo.com>
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

import transaction
from OFS.Folder import Folder
import unittest
from Testing.makerequest import makerequest
import Testing.ZopeTestCase.ZopeLite as Zope2
from Testing import ZopeTestCase

from Products.SiteAccess.VirtualHostMonster import VirtualHostMonster

from Products.CPSCore.URLTool import URLTool


ZopeTestCase.installProduct('CMFCore', quiet=1)
ZopeTestCase.installProduct('SiteAccess', quiet=1)

class URLToolTests(unittest.TestCase):

    traverse_value = '/portal/folder/doc'

    #
    # test case methods
    #

    def setUp(self):
        transaction.begin()
        self.app = makerequest(Zope2.app())

        # Add a VHM
        if not self.app.objectIds('Virtual Host Monster'):
            vhm = VirtualHostMonster()
            vhm.id = 'vhm'
            vhm.addToContainer(self.app)

        # portal
        self.app.manage_addFolder('portal')
        self.portal = self.app.portal

        # url tool
        url_tool = URLTool()
        self.url_tool = url_tool.__of__(self.portal)

        # content
        self.portal.manage_addFolder('folder')
        self.folder = self.portal.folder
        self.folder.manage_addDTMLMethod('doc', '')
        self.doc = self.folder.doc

        # REQUEST
        self.app.REQUEST.set('PARENTS', [self.app])
        self.traverse = self.app.REQUEST.traverse

        try:
            self.traverse(self.traverse_value)
        except:
            self.tearDown()
            raise

    def tearDown(self):
        self.app.REQUEST.close()
        transaction.abort()
        self.app._p_jar.close()

    #
    # tests
    #

    def test_interface(self):
        # XXX use Z3 interfaces when we switch to CMF 1.6
        from Interface.Verify import verifyClass
        from Products.CMFCore.interfaces.portal_url \
             import portal_url as IURLTool
        from Products.CMFCore.interfaces.portal_actions \
             import ActionProvider as IActionProvider

        verifyClass(IURLTool, URLTool)
        verifyClass(IActionProvider, URLTool)

    # CMF URLTool tests

    def test_getPortalObject(self):
        self.assertEqual(self.url_tool.getPortalObject(), self.portal)

    def test_getPortalPath(self):
        self.assertEqual(self.url_tool.getPortalPath(), '/portal')

    def test_getRelativeContentPath(self):
        self.assertEqual(self.url_tool.getRelativeContentPath(self.doc),
                         ('folder', 'doc'))

    def test_getRelativeContentURL(self):
        self.assertEqual(self.url_tool.getRelativeContentURL(self.doc),
                         'folder/doc')

    def test_getRelativeURL(self):
        self.assertEqual(self.url_tool.getRelativeUrl(self.doc),
                         'folder/doc')

    # CPS URLTool tests

    def test_getRpath(self):
        self.assertEqual(self.url_tool.getRpath(self.doc),
                         'folder/doc')

    def test_getUrlFromRpath(self):
        self.assertEqual(self.url_tool.getUrlFromRpath('folder/doc'),
                         self.doc.absolute_url())

    def test_getRpathFromPath(self):
        path = ('', 'portal', 'folder', 'doc')
        self.assertEqual(self.url_tool.getRpathFromPath(path),
                         'folder/doc')
        path = '/portal/folder/doc'
        self.assertEqual(self.url_tool.getRpathFromPath(path),
                         'folder/doc')

    # CPS URLTool tests that may be dependant from virtual hosting configuration

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://foo/portal')

    def test_getBaseUrl(self):
        self.assertEqual(self.url_tool.getBaseUrl(), '/portal/')

    def test_getVirtualRootPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(),
                         ('',))

    def test_getVirtualHostPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualHostPhysicalPath(),
                         ('',))

    def test_getBreadCrumbs(self):
        # portal
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=0),
                         [self.portal])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=1),
                         [self.portal])
        # folder
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=0),
                         [self.portal, self.folder])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=1),
                         [self.portal])
        # doc
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=0),
                         [self.portal, self.folder, self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      ),
                         [self.portal, self.folder, self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=1),
                         [self.portal, self.folder])

    def test_getBreadCrumbsWithoutRoot(self):
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=False,
                                                      ),
                         [self.folder, self.doc])

        # The tests below check that the good interaction between
        # the property breadcrumbs_show_root and the parameter show_root.
        self.url_tool.manage_changeProperties(breadcrumbs_show_root=False)

        # portal
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=0),
                         [])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=1),
                         [])
        # folder
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=0),
                         [self.folder])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=1),
                         [])
        # doc
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=0),
                         [self.folder, self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=1),
                         [self.folder])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      ),
                         [self.portal, self.folder, self.doc])

    def test_getBreadCrumbsWithoutHiddenFolders(self):
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      show_hidden_folders=False,
                                                      ),
                         [self.portal, self.folder, self.doc])

    def test_getBreadCrumbsWithFirstItem(self):
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      first_item=0,
                                                      ),
                         [self.portal, self.folder, self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      first_item=1,
                                                      ),
                         [self.portal, self.folder, self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      first_item=2,
                                                      ),
                         [self.portal, self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=True,
                                                      first_item=3,
                                                      ),
                         [self.portal])

        # hiding the root should not affect the other items
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=False,
                                                      first_item=0,
                                                      ),
                         [self.folder, self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=False,
                                                      first_item=1,
                                                      ),
                         [self.folder, self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=False,
                                                      first_item=2,
                                                      ),
                         [self.doc])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=False,
                                                      show_root=False,
                                                      first_item=3,
                                                      ),
                         [])

        # only_parents=True, show_root=True
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=True,
                                                      first_item=0,
                                                      ),
                         [self.portal, self.folder])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=True,
                                                      first_item=1,
                                                      ),
                         [self.portal, self.folder])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=True,
                                                      first_item=2,
                                                      ),
                         [self.portal])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=True,
                                                      first_item=3,
                                                      ),
                         [self.portal])

        # only_parents=True, show_root=False
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=False,
                                                      first_item=0,
                                                      ),
                         [self.folder])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=False,
                                                      first_item=1,
                                                      ),
                         [self.folder])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=False,
                                                      first_item=2,
                                                      ),
                         [])

        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=True,
                                                      show_root=False,
                                                      first_item=3,
                                                      ),
                         [])

class URLToolTestsVHB(URLToolTests):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/portal/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com/portal')


class URLToolTests2(URLToolTests):

    traverse_value = '/VirtualHostRoot/portal/folder/doc/'


class URLToolTests2VHB(URLToolTests2):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/VirtualHostRoot/portal/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com/portal')


class URLToolTests3(URLToolTests):

    traverse_value = '/VirtualHostRoot/_vh_truc/portal/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://foo/truc/portal')

    def test_getBaseUrl(self):
        self.assertEqual(self.url_tool.getBaseUrl(), '/truc/portal/')

    def test_getVirtualHostPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualHostPhysicalPath(),
                         ('', 'truc'))


class URLToolTests3VHB(URLToolTests3):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/VirtualHostRoot/_vh_truc/portal/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com/truc/portal')


class URLToolTests4(URLToolTests):

    traverse_value = '/portal/VirtualHostRoot/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://foo')

    def test_getBaseUrl(self):
        self.assertEqual(self.url_tool.getBaseUrl(), '/')

    def test_getVirtualRootPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(),
                         ('', 'portal'))


class URLToolTests4VHB(URLToolTests4):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/portal/VirtualHostRoot/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com')


class URLToolTests5(URLToolTests):

    traverse_value = '/portal/VirtualHostRoot/_vh_truc/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://foo/truc')

    def test_getBaseUrl(self):
        self.assertEqual(self.url_tool.getBaseUrl(), '/truc/')

    def test_getVirtualRootPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(),
                         ('', 'portal'))

    def test_getVirtualHostPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualHostPhysicalPath(),
                         ('', 'truc'))

class URLToolTests5VHB(URLToolTests5):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/portal/VirtualHostRoot/_vh_truc/folder/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com/truc')


class URLToolTests6(URLToolTests):

    traverse_value = '/portal/folder/VirtualHostRoot/_vh_truc/_vh_bidule/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://foo/truc/bidule')

    def test_getBaseUrl(self):
        self.assertEqual(self.url_tool.getBaseUrl(), '/truc/bidule/')

    def test_getVirtualRootPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(),
                         ('', 'portal', 'folder'))

    def test_getVirtualHostPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualHostPhysicalPath(),
                         ('', 'truc', 'bidule'))

    def test_getBreadCrumbs(self):
        # portal is not supposed to be seen because folder is the virtual root
        # portal, even this is awkward
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=0),
                         [self.folder])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=1),
                         [self.folder])
        # folder
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=0),
                         [self.folder])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=1),
                         [self.folder])
        # doc
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=0),
                         [self.folder, self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=1),
                         [self.folder])

    def test_getBreadCrumbsWithoutRoot(self):
        self.url_tool.manage_changeProperties(breadcrumbs_show_root=False)
        # portal
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=0),
                         [])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=1),
                         [])
        # folder
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=0),
                         [])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=1),
                         [])
        # doc
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=0),
                         [self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=1),
                         [])

    def test_getBreadCrumbsWithoutHiddenFolders(self):
        pass

    def test_getBreadCrumbsWithFirstItem(self):
        pass

class URLToolTests6VHB(URLToolTests6):

    traverse_value = '/VirtualHostBase/http/www.site.com:80/portal/folder/VirtualHostRoot/_vh_truc/_vh_bidule/doc/'

    def test_tool_call(self):
        self.assertEqual(self.url_tool(), 'http://www.site.com/truc/bidule')


def test_suite():
    from inspect import isclass
    tests = []
    for obj in globals().values():
        if isclass(obj) and issubclass(obj, URLToolTests):
            tests.append(unittest.makeSuite(obj))
    return unittest.TestSuite(tests)

if __name__ == "__main__":
    unittest.main(defaultTest='test_suite')
