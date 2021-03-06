# -*- coding: iso-8859-15 -*-
"""Dummy (= Mock) classes for unit tests"""

from OFS.SimpleItem import SimpleItem
from OFS.Folder import Folder

class DummyRoot(Folder):
    def _getProductRegistryData(self, name):
        if name == 'ac_permissions':
            return (('Modify', (), ('Manager',)),
                    ('DoStuff', (), ('Manager',)),)
        return ValueError(name)

    def getPhysicalRoot(self):
        return self

class DummyWorkflowTool(SimpleItem):
    def getManagedPermissions(self):
        return ['View', 'Modify', 'DoStuff']

class DummyPortalUrl(SimpleItem):
    def getPortalObject(self):
        return self.aq_parent

class Dummy(SimpleItem):
    def __init__(self, id, data=None):
        self._id = id
        self._data = data

    def getId(self):
        return self._id

    def getData(self):
        return self._data

    def reindexObject(self, idxs=[]):
        pass

    def reindexObjectSecurity(self, skip_self=False):
        pass

    def _reindexObject(self, idxs=[]):
        pass

    def _reindexObjectSecurity(self, skip_self=False):
        pass

class DummyTypeInfo(Dummy):
    pass

class DummyContent(Dummy):
    meta_type = 'Dummy'
    _isPortalContent = 1

    def _getPortalTypeName(self):
        return 'Dummy Content'

class DummyTypesTool(SimpleItem):
    def listTypeInfo(self):
        return [DummyTypeInfo('Dummy Content')]

    def getTypeInfo(self, ob):
        if (ob == 'Dummy Content' or
            getattr(ob, 'meta_type', None) == 'Dummy'):
            return DummyTypeInfo('Dummy Content')
        return None

class DummyObjectRepositoryTool(Folder):
    _last_calls = {}

    def createRevision(self, docid, type_name, *args, **kw):
        self._last_calls['createRevision'] = {'docid': docid,
                                              'type_name': type_name,
                                              'args': args,
                                              'kw': kw}
        rev = 17

        id = 'ob_%s_%s' % (docid, rev)  #Copy/Paste from DummyProxyTool
        if id not in self.objectIds():
            doc = SimpleItem(id)
            doc._setId(id)
            doc.portal_type = 'Some Type'
            self._setObject(id, doc)
        return self._getOb(id), rev

    def getFreeDocid(self):
        return 'a free docid from repotool'

    def isObjectInRepository(self, ob):
        return ob in self.objectValues()

