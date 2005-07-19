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

import unittest
from Testing.makerequest import makerequest

import Zope
Zope.startup()

from OFS.Folder import Folder

from Interface.Verify import verifyClass
from Products.CPSCore.URLTool import URLTool
from Products.CPSCore.CPSMembershipTool import CPSMembershipTool

class URLToolTests(unittest.TestCase):

    #
    # test case methods
    #

    def setUp(self):
        get_transaction().begin()
        self.app = makerequest(Zope.app())

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

    def tearDown(self):
        get_transaction().abort()
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

    def test_getPortalObject(self):
        self.assertEqual(self.url_tool.getPortalObject(), self.portal)

    def test_getPortalPath(self):
        self.assertEqual(self.url_tool(), 'http://foo/portal')
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

    def test_getBaseURL(self):
        self.assertEqual(self.url_tool.getBaseURL(), '/portal/')

    def test_getVirtualRootPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(),
                         ('',))

    def test_getVirtualHostPhysicalPath(self):
        self.assertEqual(self.url_tool.getVirtualHostPhysicalPath(),
                         ('',))

    def test_getAbsoluteURLFromRelativeURL(self):
        self.assertEqual(self.url_tool.getAbsoluteURLFromRelativeURL('folder/doc'),
                         self.doc.absolute_url())

    def test_getBreadCrumbs(self):
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=0),
                         [self.portal, self.folder, self.doc])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                      only_parents=1),
                         [self.portal, self.folder])

#
# Generate different cases of virtual hosting
#

def gen_cases():
    for vbase, ubase in (
        # foo is the app name in makerequest
        ('', 'http://foo'),
        ('/VirtualHostBase/http/www.site.com:80', 'http://www.site.com'),
        ):
        yield vbase, '', '', 'portal/folder/doc', ubase
        for vr, _vh, content in (
            ('', '', 'portal/folder/doc'),
            ('', 'truc', 'portal/folder/doc'),
            ('portal', '', 'folder/doc'),
            ('portal', 'truc', 'folder/doc'),
            # more complicated case, not handled right now
            ('portal/folder', 'truc/bidule', 'doc'),
            ):
            vparts = [vbase, vr, 'VirtualHostRoot']
            if not vr:
                del vparts[1]
            if _vh:
                new_vh = '/'.join(['_vh_' + x for x in _vh.split('/')])
                vparts.append(new_vh)
            yield '/'.join(vparts), vr, _vh, content, ubase

for i, (vaddr, vr, _vh, content, ubase) in enumerate(gen_cases()):
    def test(self, vaddr=vaddr, vr=vr, _vh=_vh,
             content=content, ubase=ubase, i=i):

        # get the object, sets the REQUEST
        ob = self.traverse('%s/%s/' % (vaddr, content))

        # helpers

        # slashed content
        new_content = content
        if vr and content.startswith(vr):
            new_content = content[len(vr):]
        sl_content = (new_content and ('/' + new_content))

        # slashed virtual host
        sl_vh = (_vh and ('/' + _vh))

        # absolute url path
        aup = sl_vh + sl_content

        # debug prints

        #print "\n%s" %(i,)
        #print "ubase=%s"%(ubase)
        #print "vaddr=%s"%(vaddr)
        #print "vr=%s"%(vr)
        #print "_vh=%s"%(_vh)
        #print "content=%s"%(content)
        #print "aup=%s"%(aup,)
        #print "\n"

        #
        # OFS.Traversable methods tests
        #

        # object (file)
        self.assertEqual(ob.getPhysicalPath(), ('', 'portal', 'folder', 'doc'))
        self.assertEqual(ob.absolute_url(), ubase + aup)
        self.assertEqual(ob.absolute_url(relative=1), content)
        self.assertEqual(ob.absolute_url_path(), aup)
        self.assertEqual(ob.virtual_url_path(), content)
        self.assertEqual(self.app.REQUEST['BASEPATH1'] + '/' + content, aup)

        #
        # URLTool methods tests
        #

        # portal
        self.assertEqual(self.url_tool.getPortalObject(), self.portal)

        # independant from virtual hosting
        self.assertEqual(self.url_tool.getPortalPath(), '/portal')
        self.assertEqual(self.url_tool.getRelativeContentPath(self.doc),
                         ('folder', 'doc'))
        self.assertEqual(self.url_tool.getRelativeContentURL(self.doc),
                         'folder/doc')
        self.assertEqual(self.url_tool.getRelativeUrl(self.doc),
                         'folder/doc')

        # virtual root
        add_portal_id = 1
        if vr:
            vr_list = vr.split('/')
            if vr_list and vr_list[0] == 'portal':
                add_portal_id = 0

        # compute url_tool call
        urltool_call = ubase
        # add virtual host
        if _vh:
            urltool_call += '/' + _vh
        if add_portal_id:
            urltool_call += '/portal'

        self.assertEqual(self.url_tool(), urltool_call)

        base_url = ''
        if _vh:
            base_url += '/' + _vh
        if add_portal_id:
            base_url += '/portal'
        base_url += '/'
        self.assertEqual(self.url_tool.getBaseURL(), base_url)

        vrph = ('',)
        if vaddr.find('VirtualHostRoot') != -1 and vr:
            vrph = tuple(('/' + vr).split('/'))
        self.assertEqual(self.url_tool.getVirtualRootPhysicalPath(), vrph)

        self.assertEqual(self.url_tool.getAbsoluteURLFromRelativeURL('folder/doc'),
                         self.doc.absolute_url())

        # breadcrumbs

        # portal
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=0),
                         [self.portal])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.portal,
                                                      only_parents=1),
                         [self.portal])
        # folder

        # sometimes folder cannot be seen because it is hidden by virtual host
        # root
        vrpp = self.url_tool.getVirtualRootPhysicalPath()
        if len(vrpp)>2:
            hide_folder = 1
        else:
            hide_folder = 0

        if hide_folder:
            self.assertEqual([x.getId() for x in self.url_tool.getBreadCrumbs(context=self.folder,
                                                          only_parents=0)],
                             [self.portal.getId()])
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                          only_parents=0),
                             [self.portal])
        else:
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                          only_parents=0),
                             [self.portal, self.folder])
        self.assertEqual(self.url_tool.getBreadCrumbs(context=self.folder,
                                                      only_parents=1),
                         [self.portal])
        # doc
        if hide_folder:
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                          only_parents=0),
                             [self.portal, self.doc])
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                          only_parents=1),
                             [self.portal])
        else:
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                          only_parents=0),
                             [self.portal, self.folder, self.doc])
            self.assertEqual(self.url_tool.getBreadCrumbs(context=self.doc,
                                                          only_parents=1),
                             [self.portal, self.folder])

    setattr(URLToolTests, 'testTraverse%s' % i, test)

def test_suite():
    suites = []
    suites.append(unittest.makeSuite(URLToolTests))
    return unittest.TestSuite(suites)

if __name__=="__main__":
    unittest.main(defaultTest='test_suite')
