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
#

import unittest
from Testing.makerequest import makerequest

try:
    import Zope2
except ImportError: # BBB: for Zope 2.7
    import Zope as Zope2

Zope2.startup()

from OFS.Folder import Folder

from Interface.Verify import verifyClass
from Products.CPSCore.URLTool import URLTool
from Products.CPSCore.CPSMembershipTool import CPSMembershipTool

try:
    import transaction
except ImportError: # BBB: for Zope 2.7
    from Products.CMFCore.utils import transaction



class URLToolTests(unittest.TestCase):

    traverse_value = '/portal/folder/doc'

    #
    # test case methods
    #

    def setUp(self):
        transaction.begin()
        self.app = makerequest(Zope2.app())

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

        self.traverse(self.traverse_value)

    def tearDown(self):
        self.app.REQUEST.close()
        transaction.abort()
        self.app._p_jar.close()

    #
    # tests
    #

    def test_interface(self):
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
                                                      only_parents=1),
                         [self.portal, self.folder])

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

if __name__=="__main__":
    unittest.main(defaultTest='test_suite')
