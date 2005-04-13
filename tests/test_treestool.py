# -*- coding: iso-8859-15 -*-
# Copyright (C) 2004-2005 Nuxeo SARL <http://nuxeo.com>
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
from OFS.OrderedFolder import OrderedFolder

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from Products.CPSCore.TreesTool import TreesTool, TreeCache


class DummyTreeCache(SimpleItem):
    notified = 0
    def notify_tree(self, event_type, ob, infos):
        self.notified = self.notified + 1

class DummyObject(OrderedFolder):
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

    def test_isCandidate(self):
        ppath = '/cmf'.split('/')
        plen = len(ppath)
        cache = self.makeOne()

        ob = DummyObject(path='/cmf/root/foo')
        self.assert_(cache._isCandidate(ob, plen))
        ob = DummyObject(path='/cmf/root/foo/bar')
        self.assert_(cache._isCandidate(ob, plen))
        ob = DummyObject(path='/cmf/root/bar')
        self.failIf(cache._isCandidate(ob, plen))
        # We'll never be notified outside of the portal anyway
        #ob = DummyObject(path='/moo/root/foo/bar')
        #self.failIf(cache._isCandidate(ob, plen))

        ob = DummyObject(path='/cmf/root/foo')
        ob.portal_type = 'Ah'
        self.failIf(cache._isCandidate(ob, plen))
        ob = DummyObject(path='/cmf/root/foo')
        ob.meta_type = 'Hehe'
        self.failIf(cache._isCandidate(ob, plen))


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

        # fake acl_users
        app.acl_users = Folder()

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


    def test_rebuild(self):
        # Test rebuilding a tree
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cmf.root.foo._setObject('baz', DummyObject('baz', title='Baz'))

        cache.rebuild()
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])

    def test_upgrade(self):
        # Test upgrade of an old-style tree
        self.makeInfrastructure()
        cmf = self.app.cmf
        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cache = cmf.cache

        # Setup old data
        cache._tree = [] # dummy
        cache._pointers = [] # dummy
        cache._flat = [
            {'rpath': 'root/foo',
             'children': ['recompute_this'],
             'depth': 0,
             'allowed_roles_and_users': ['Manager'],
             },
            # missing info for 'root/foo/bar'
            ]

        cache._maybeUpgrade()
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1])

    def test_event_sys_add_cmf_object(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add root first
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        l = cache.getList(filter=False)
        self.assertEquals(l, [{
            'allowed_roles_and_users': ['Manager'],
            'depth': 0,
            'id': 'foo',
            'local_roles': {},
            'nb_children': 0,
            'portal_type': 'ThePortalType',
            'rpath': 'root/foo',
            'title': 'Foo',
            'visible': False,
            }])
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo'])

        # Add first child
        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Bar'])
        self.assertEquals([d['nb_children'] for d in l],
                          [1, 0])

        # Add another
        cmf.root.foo._setObject('baz', DummyObject('baz', title='Baz'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.baz, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Bar', 'Baz'])
        self.assertEquals([d['nb_children'] for d in l],
                          [2, 0, 0])

        # Check re-add existing one
        cmf.root.foo._delObject('bar')
        cmf.root.foo._setObject('bar', DummyObject('bar', title='NewBar'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/baz', 'root/foo/bar'])
        self.assertEquals([d['depth'] for d in l],
                          [0, 1, 1])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Baz', 'NewBar'])

        # Check without ordering
        l = cache.getList(filter=False, order=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/baz'])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'NewBar', 'Baz'])

    def test_event_sys_del_object(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['nb_children'] for d in l],
                          [1, 0])

        # Delete child
        cache.notify_tree('sys_del_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo'])
        self.assertEquals([d['nb_children'] for d in l],
                          [0])

        # Delete root itself
        cache.notify_tree('sys_del_object', cmf.root.foo, {})
        l = cache.getList(filter=False)
        self.assertEquals(l, [])

    def test_event_sys_order_object(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        cmf.root.foo.bar._setObject('b', DummyObject('b', title='B'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar.b, {})
        cmf.root.foo._setObject('baz', DummyObject('baz', title='Baz'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.baz, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar', 'root/foo/bar/b',
                           'root/foo/baz'])

        # Reorder children
        cmf.root.foo.moveObjectsDown('bar')
        cache.notify_tree('sys_order_object', cmf.root.foo, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/baz', 'root/foo/bar',
                           'root/foo/bar/b'])

    def test_event_sys_modify_security(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        prebar = DummyObject('bar', title='Bar')
        cmf.root.foo._setObject('bar', prebar)
        bar = cmf.root.foo.bar
        cache.notify_tree('sys_add_cmf_object', bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['allowed_roles_and_users'] for d in l],
                          [['Manager'], ['Manager']])
        self.assertEquals([d['local_roles'] for d in l],
                          [{}, {'user:Anonymous User': ('Owner',)}])

        # Change security
        bar._View_Permission = ('SomeRole',)
        bar.__ac_local_roles__ = {'bob': ['SomeRole']}
        cache.notify_tree('sys_modify_security', bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['allowed_roles_and_users'] for d in l],
                          [['Manager'], ['SomeRole', 'user:bob']])
        self.assertEquals([d['local_roles'] for d in l],
                          [{}, {'user:bob': ('SomeRole',)}])


    def test_event_modify_object(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Add
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo, {})
        cmf.root.foo._setObject('bar', DummyObject('bar', title='Bar'))
        cache.notify_tree('sys_add_cmf_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo', 'root/foo/bar'])
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'Bar'])

        # Change
        cmf.root.foo._delObject('bar')
        cmf.root.foo._setObject('bar', DummyObject('bar', title='NewBar'))
        cache.notify_tree('modify_object', cmf.root.foo.bar, {})
        l = cache.getList(filter=False)
        self.assertEquals([d['title'] for d in l],
                          ['Foo', 'NewBar'])
        self.assertEquals(l[1], {
            'allowed_roles_and_users': ['Manager'],
            'depth': 1,
            'id': 'bar',
            'local_roles': {'user:Anonymous User': ('Owner',)},
            'nb_children': 0,
            'portal_type': 'ThePortalType',
            'rpath': 'root/foo/bar',
            'title': 'NewBar',
            'visible': False,
            })

    def makeDeepStructure(self):
        self.makeInfrastructure()
        cmf = self.app.cmf
        cache = cmf.cache

        # Build structure
        foo = cmf.root.foo
        # Visible at root
        foo._View_Permission = ('Anonymous',)
        # Rest
        foo._setObject('baz', DummyObject('baz', title='Baz'))
        foo._setObject('bar', DummyObject('bar', title='Bar'))
        foo.bar._setObject('b', DummyObject('b', title='B'))
        foo.bar.b._setObject('z', DummyObject('z', title='Z'))
        foo.bar.b._setObject('d', DummyObject('d', title='D'))
        foo.bar.b.d._setObject('d2', DummyObject('d2', title='D2'))
        foo.bar.b.d._setObject('d1', DummyObject('d1', title='D1'))
        # Change security in the middle
        d = foo.bar.b.d
        d._View_Permission = ('SomeRole',)
        d.__ac_local_roles__ = {'bob': ['SomeRole']}
        # Add them
        for ob in (foo,
                   foo.bar,
                   foo.baz,
                   foo.bar.b,
                   foo.bar.b.z,
                   foo.bar.b.d,
                   foo.bar.b.d.d2,
                   foo.bar.b.d.d1,
                   ):
            cache.notify_tree('sys_add_cmf_object', ob, {})

        return cache

    def test_deep_no_filtering(self):
        # Without visibility filtering
        cache = self.makeDeepStructure()

        # without children
        l = cache.getList(filter=False, order=False, count_children=False)
        self.assertEquals([(d['rpath'], d['visible']) for d in l],
                          [('root/foo',            True),
                           ('root/foo/bar',        True),
                           ('root/foo/bar/b',      True),
                           ('root/foo/bar/b/d',    False),
                           ('root/foo/bar/b/d/d1', False),
                           ('root/foo/bar/b/d/d2', False),
                           ('root/foo/bar/b/z',    True),
                           ('root/foo/baz',        True),
                           ])
        l = cache.getList(filter=False, order=True, count_children=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo',
                           'root/foo/baz',
                           'root/foo/bar',
                           'root/foo/bar/b',
                           'root/foo/bar/b/z',
                           'root/foo/bar/b/d',
                           'root/foo/bar/b/d/d2',
                           'root/foo/bar/b/d/d1',
                           ])

        # with children
        l = cache.getList(filter=False, order=False, count_children=True)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo',            2),
                           ('root/foo/bar',        1),
                           ('root/foo/bar/b',      2),
                           ('root/foo/bar/b/d',    2),
                           ('root/foo/bar/b/d/d1', 0),
                           ('root/foo/bar/b/d/d2', 0),
                           ('root/foo/bar/b/z',    0),
                           ('root/foo/baz',        0),
                           ])
        l = cache.getList(filter=False, order=True, count_children=True)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo',            2),
                           ('root/foo/baz',        0),
                           ('root/foo/bar',        1),
                           ('root/foo/bar/b',      2),
                           ('root/foo/bar/b/z',    0),
                           ('root/foo/bar/b/d',    2),
                           ('root/foo/bar/b/d/d2', 0),
                           ('root/foo/bar/b/d/d1', 0),
                           ])

        # depth and prefix filtering
        l = cache.getList(filter=False, order=False, count_children=False,
                          prefix='root/foo/bar/b')
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo/bar/b',
                           'root/foo/bar/b/d',
                           'root/foo/bar/b/d/d1',
                           'root/foo/bar/b/d/d2',
                           'root/foo/bar/b/z',
                           ])
        l = cache.getList(filter=False, order=False, count_children=False,
                          start_depth=2)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo/bar/b',
                           'root/foo/bar/b/d',
                           'root/foo/bar/b/d/d1',
                           'root/foo/bar/b/d/d2',
                           'root/foo/bar/b/z',
                           ])
        l = cache.getList(filter=False, order=False, count_children=False,
                          start_depth=2, stop_depth=3)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo/bar/b',
                           'root/foo/bar/b/d',
                           'root/foo/bar/b/z',
                           ])
        l = cache.getList(filter=False, order=False, count_children=True,
                          start_depth=1, stop_depth=2)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo/bar',   1),
                           ('root/foo/bar/b', 0),
                           ('root/foo/baz',   0),
                           ])


    def test_deep_with_filtering(self):
        # With visibility filtering, not visible starting from d
        cache = self.makeDeepStructure()

        # without children
        l = cache.getList(filter=True, order=False, count_children=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo',
                           'root/foo/bar',
                           'root/foo/bar/b',
                           'root/foo/bar/b/z',
                           'root/foo/baz',
                           ])
        l = cache.getList(filter=True, order=True, count_children=False)
        self.assertEquals([d['rpath'] for d in l],
                          ['root/foo',
                           'root/foo/baz',
                           'root/foo/bar',
                           'root/foo/bar/b',
                           'root/foo/bar/b/z',
                           ])

        # with children
        l = cache.getList(filter=True, order=False, count_children=True)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo',            2),
                           ('root/foo/bar',        1),
                           ('root/foo/bar/b',      1),
                           ('root/foo/bar/b/z',    0),
                           ('root/foo/baz',        0),
                           ])
        l = cache.getList(filter=True, order=True, count_children=True)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo',            2),
                           ('root/foo/baz',        0),
                           ('root/foo/bar',        1),
                           ('root/foo/bar/b',      1),
                           ('root/foo/bar/b/z',    0),
                           ])

        # depth and prefix filtering
        l = cache.getList(filter=True, order=False, count_children=True,
                          prefix='root/foo/bar/b')
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo/bar/b',   1),
                           ('root/foo/bar/b/z', 0),
                           ])
        l = cache.getList(filter=True, order=False, count_children=True,
                          start_depth=2)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo/bar/b',   1),
                           ('root/foo/bar/b/z', 0),
                           ])
        l = cache.getList(filter=True, order=False, count_children=True,
                          start_depth=1, stop_depth=2)
        self.assertEquals([(d['rpath'], d['nb_children']) for d in l],
                          [('root/foo/bar',   1),
                           ('root/foo/bar/b', 0),
                           ('root/foo/baz',   0),
                           ])




def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreesToolTest),
        unittest.makeSuite(TreeCacheTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
