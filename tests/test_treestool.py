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

from Products.CMFCore.tests.base.testcase import SecurityRequestTest
from OFS.SimpleItem import SimpleItem

from Products.CPSCore.TreesTool import TreesTool, TreeCache


class DummyTreeCache(SimpleItem):
    notified = 0
    def notify_tree(self, event_type, ob, infos):
        self.notified = self.notified + 1

class DummyObject:
    portal_type = 'ThePortalType'
    meta_type = 'TheMetaType'
    def __init__(self, path='/dummy'):
        self.path = tuple(path.split('/'))
    def getPhysicalPath(self):
        return self.path
    def getId(self):
        return self.path[-1]


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

        ob = DummyObject('/cmf/root/foo')
        self.assert_(cache._is_candidate(ob, plen))
        ob = DummyObject('/cmf/root/foo/bar')
        self.assert_(cache._is_candidate(ob, plen))
        ob = DummyObject('/cmf/root/bar')
        self.failIf(cache._is_candidate(ob, plen))
        # We'll never be notified outside of the portal anyway
        #ob = DummyObject('/moo/root/foo/bar')
        #self.failIf(cache._is_candidate(ob, plen))

        ob = DummyObject('/cmf/root/foo')
        ob.portal_type = 'Ah'
        self.failIf(cache._is_candidate(ob, plen))
        ob = DummyObject('/cmf/root/foo')
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

    def _test_rebuild(self):
        pass

    def _test_getTree(self):
        pass

    def _test_getList(self):
        pass

def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TreesToolTest),
        unittest.makeSuite(TreeCacheTest),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
