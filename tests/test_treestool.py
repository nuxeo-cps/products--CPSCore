# -*- coding: iso-8859-15 -*-
# Copyright (C) 2004 Nuxeo SARL <http://nuxeo.com>
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
"""Tests for the trees tool.
"""

import Testing.ZopeTestCase.ZopeLite as Zope
import unittest

from Acquisition import aq_parent, aq_inner
from OFS.SimpleItem import SimpleItem
from OFS.Folder import Folder

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from Products.CPSCore.TreesTool import TreesTool, TreeCache


class DummyTreeCache(SimpleItem):
    notified = 0
    def notify_tree(self, event_type, ob, infos):
        self.notified = self.notified + 1

class DummyObject(Folder):
    portal_type = 'ThePortalType'
    meta_type = 'TheMetaType'
    def __init__(self, id=None, path=None, title=''):
        if path is not None:
            path = tuple(path.split('/'))
        if id is None and path is not None:
            id = path[-1]
        if id is None:
            id = 'dummy'
        self.id = id
        self.path = path
        self.title = title
    def getPhysicalPath(self):
        if self.path is not None:
            return self.path
        else:
            return Folder.getPhysicalPath(self)
    def get_local_group_roles(self):
        return {}

class DummyUrlTool(Folder):
    id = 'portal_url'
    def getPortalObject(self):
        return aq_parent(aq_inner(self))
    def getRelativeUrl(self, ob):
        pplen = len(self.getPortalObject().getPhysicalPath())
        path = ob.getPhysicalPath()
        return '/'.join(path[pplen:])

class DummyMembershipTool(SimpleItem):
    def getAuthenticatedMember(self):
        return DummyMember().__of__(self)
    def getAllowedRolesAndUsersOfUser(self, user):
        return ['Anonymous', 'group:role:Anonymous', 'user:dummy']

class DummyMember(SimpleItem):
    def getUser(self):
        return self


def flatkeys(tree, key='rpath'):
    rpath = tree[key]
    children = tree['children']
    if not children:
        return rpath
    else:
        return (rpath, tuple([flatkeys(child, key=key)
                              for child in children]))

class TreesToolTest(unittest.TestCase):

    def test_propagated_events(self):
        # Test that suitable events are propagated to the caches
        tool = TreesTool()
        cache1 = DummyTreeCache()
        cache2 = DummyTreeCache()
        tool._setObject('cache1', cache1)
        tool._setObject('cache2', cache2)
        interesting = (
            'sys_add_cmf_object',
            'sys_del_object',
            'sys_modify_object',
            'sys_modify_security',
            'sys_order_object',
            'modify_object',
            )
        for event_type in interesting:
            tool.notify_tree(event_type, DummyObject(), {})
        self.assertEquals(cache1.notified, len(interesting))
        self.assertEquals(cache2.notified, len(interesting))
        cache1.notified = cache2.notified = 0
        other = (
            'foo',
            'sys_add_something',
            'sys_modify_your_hair',
            'modify_car',
            )
        for event_type in other:
            tool.notify_tree(event_type, DummyObject(), {})
        self.assertEquals(cache1.notified, 0)
        self.assertEquals(cache2.notified, 0)


class TreeCacheTest(SecurityRequestTest):

    def makeOne(self):
        cache = TreeCache('treecache')
        cache.manage_changeProperties(
            root='root/foo',
            type_names=('ThePortalType',),
            meta_types=('TheMetaType',),
            )
        return cache

    def test_is_candidate(self):
        ppath = '/cmf'.split('/')
        plen = len(ppath)
        cache = self.makeOne()

        ob = DummyObject(path='/cmf/root/foo')
        self.assert_(cache._is_candidate(ob, plen))
        ob = DummyObject(path='/cmf/root/foo/bar')
        self.assert_(cache._is_candidate(ob, plen))
        ob = DummyObject(path='/cmf/root/bar')
        self.failIf(cache._is_candidate(ob, plen))
        # We'll never be notified outside of the portal anyway
        #ob = DummyObject(path='/moo/root/foo/bar')
        #self.failIf(cache._is_candidate(ob, plen))

        ob = DummyObject(path='/cmf/root/foo')
        ob.portal_type = 'Ah'
        self.failIf(cache._is_candidate(ob, plen))
        ob = DummyObject(path='/cmf/root/foo')
        ob.meta_type = 'Hehe'
        self.failIf(cache._is_candidate(ob, plen))


    def test_getRoot(self):
        cache = self.makeOne()
        self.assertEquals(cache.getRoot(), 'root/foo')
        cache.root = 'root/beer/'
        self.assertEquals(cache.getRoot(), 'root/beer')
        # Anti-loser measures
        # (Should be done at changeProperties time)
        # No going up
        cache.root = 'root/../../hack'
        self.assertEquals(cache.getRoot(), '')
        # No absolute path
        cache.root = '/hack/this'
        self.assertEquals(cache.getRoot(), '')

    def makeInfrastructure(self):
        app = Folder()
        app._setId('')
        self.app = app

        cmf = Folder()
        cmf._setId('cmf')
        app.cmf = cmf
        cmf = app.cmf # Wrap

        cmf.portal_url = DummyUrlTool()
        cmf.portal_membership = DummyMembershipTool()

        cache = self.makeOne()
        cmf.cache = cache
        cache = cmf.cache # Wrap

        cache.manage_changeProperties(info_method='info_method')
        def info_method(doc=None):
            return {
                'title': doc.title,
                }
        cmf.info_method = info_method

        # Build root hierarchy
        cmf.root = DummyObject('root')
        cmf.root.foo = DummyObject('foo', title='Foo')

    def test_inserts(self):
        # Test basic use.
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add root first
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        l = cache.getList(filter=0)
        self.assertEquals(l, [{
            'allowed_roles_and_users': ['Manager'],
            'depth': 0,
            'id': 'foo',
            'local_roles': {},
            'nb_children': 0,
            'path': '/cmf/root/foo',
            'portal_type': 'ThePortalType',
            'rpath': 'root/foo',
            'title': 'Foo',
            'url': 'cmf/root/foo',
            'visible': 0,
            }])
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo'])

        # Add first child
        cmf.root.foo.bar = DummyObject('bar', title='Bar')
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=0)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Bar'])

        # Add another
        cmf.root.foo.baz = DummyObject('baz', title='Baz')
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.baz, {})
        l = cache.getList(filter=0)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Bar', 'Baz'])

        # Check re-add existing one
        cmf.root.foo.bar = DummyObject('bar', title='NewBar')
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=0)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])
        #self.assertEquals([d['title'] for d in l],  # XXX
        #                  ['Foo', 'NewBar', 'Baz']) # XXX

    def test_rebuild(self):
        # Test rebuilding a tree
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cmf.root.foo._setObject('baz', DummyObject('baz', title='Baz'))

        cache.rebuild()
        l = cache.getList(filter=0)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])

    def _test_getList(self):
        pass

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreesToolTest),
        unittest.makeSuite(TreeCacheTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
