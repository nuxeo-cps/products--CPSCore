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

class DummyRepo(SimpleItem):
    def __init__(self):
        self.sec = {}

    def getObjectVersion(self, repoid, version_info):
        return 'ob_%s_%s' % (repoid, version_info)

    def setRevisionSecurity(self, docid, rev, userperms):
        self.sec['%s.%s' % (docid, rev)] = userperms
        return 1

    def _testClearSecurity(self):
        self.sec = {}

    def _testGetSecurity(self):
        return self.sec

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

class DummySubscriber(SimpleItem):

    id = 'portal_subscriber'

    meta_type = 'Dummy Subscriber'

    notified = 0
    object = None
    event_type = None
    infos = None

    def notify_action(self, event_type, object, infos):
        self.notified += 1
        self.object = object
        self.event_type = event_type
        self.infos = infos

