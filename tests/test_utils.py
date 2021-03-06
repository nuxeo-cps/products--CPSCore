import unittest
from Testing import ZopeTestCase

from Products.CPSCore import utils
from Products.CPSCore.ProxyBase import ProxyFolder
from Products.CPSCore.ProxyBase import ProxyBTreeFolder
from Products.CPSCore.ProxyBase import ProxyDocument

def add(klass, container, oid, **kw):
    ob = klass(oid, **kw)
    container._setObject(ob.getId(), ob)
    return ob.getId()

class Test(unittest.TestCase):

    def test_mergedLocalRolesManipulation(self):
        # The _mergedLocalRoles function used to return references to
        # actual local role settings and it was possible to manipulate them
        # by changing the return value. http://www.zope.org/Collectors/CMF/376
        from Products.CMFCore.tests.base.dummy import DummyContent
        from Products.CPSCore.utils import mergedLocalRoles
        obj = DummyContent()
        obj.manage_addLocalRoles('dummyuser1', ['Manager', 'Owner'])
        self.assertEqual(len(obj.get_local_roles_for_userid('dummyuser1')), 2)

        merged_roles = mergedLocalRoles(obj)
        merged_roles['dummyuser1'].append('FOO')

        # The values on the object itself should still the the same
        self.assertEqual(len(obj.get_local_roles_for_userid('dummyuser1')), 2)

class TestWalk(ZopeTestCase.ZopeTestCase):

    def afterSetUp(self):
        pass

    def test_walk(self):
        add(ProxyFolder, self.folder, 'a')
        add(ProxyFolder, self.folder, 'b')
        add(ProxyDocument, self.folder, 'c')
        add(ProxyBTreeFolder, self.folder.a, 'abt')
        for x in range(10):
            add(ProxyDocument, self.folder.a.abt, 'abtc%d' % x)
        add(ProxyFolder, self.folder.a.abt, 'abtf')
        add(ProxyFolder, self.folder.b, 'ba')

        gen = utils.walk(self.folder, meta_types=('CPS Proxy Folder',))
        self.assertEquals([f.getId() for f in gen], ['a', 'b', 'ba'])

        gen = utils.walk(self.folder, meta_types=('CPS Proxy Folder',
                                                  'CPS Proxy BTree Folder'))
        self.assertEquals([f.getId() for f in gen],
                          ['a', 'abt', 'abtf', 'b', 'ba'])

    def test_iterValues(self):
        # TODO: to be moved and adapted to test_base
        add(ProxyBTreeFolder, self.folder, 'bt')
        bt = self.folder.bt
        oids = ['abtc%d' % x for x in range(10)]
        for oid in oids:
            add(ProxyDocument, bt, oid)
        self.assertEquals([o.getId() for o in bt.iterValues()], oids)


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(Test),
        unittest.makeSuite(TestWalk)))


if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
