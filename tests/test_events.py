# (C) Copyright 2005 Nuxeo SAS <http://nuxeo.com>
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
"""Test events in CPS
"""

import unittest
from zope.testing import doctest

import Testing.ZopeTestCase

from Products.CPSCore.tests import setup

import Acquisition
from OFS.SimpleItem import SimpleItem
from OFS.Folder import Folder
from OFS.OrderedFolder import OrderedFolder
from Products.BTreeFolder2.BTreeFolder2 import BTreeFolder2

class MyApp(Folder):
    def getPhysicalRoot(self):
        return self

class MyFolder(Folder):
    def _verifyObjectPaste(self, object, validate_src=1):
        pass
    def cb_isMoveable(self):
        return True
    def cb_isCopyable(self):
        return True

class MyOrderedFolder(OrderedFolder):
    def _verifyObjectPaste(self, object, validate_src=1):
        pass

class MyBTreeFolder(BTreeFolder2):
    def _verifyObjectPaste(self, object, validate_src=1):
        pass

class MyContent(SimpleItem):
    def __init__(self, id):
        self._setId(id)
    def cb_isMoveable(self):
        return True
    def cb_isCopyable(self):
        return True


def test_events():
    """
    A bit of setup for the tests::

      >>> root = setup.eventObserverSetUp()

    Prepare root folders::

      >>> app = MyApp('')
      >>> root['app'] = app
      >>> folder = MyFolder('folder')
      >>> app._setObject('folder', folder)
      ObjectWillBeAddedEvent folder
      ObjectAddedEvent folder
      ContainerModifiedEvent
      'folder'
      >>> folder = app.folder

    Add and remove::

      >>> ob = MyContent('batman')
      >>> folder._setObject('batman', ob)
      ObjectWillBeAddedEvent batman
      ObjectAddedEvent batman
      ContainerModifiedEvent folder
      'batman'
      >>> folder.manage_delObjects('batman')
      ObjectWillBeRemovedEvent batman
      ObjectRemovedEvent batman
      ContainerModifiedEvent folder

    Move::

      >>> ob = MyContent('dilbert')
      >>> folder._setObject('dilbert', ob)
      ObjectWillBeAddedEvent dilbert
      ObjectAddedEvent dilbert
      ContainerModifiedEvent folder
      'dilbert'
      >>> cp = folder.manage_cutObjects('dilbert')
      >>> folder.manage_pasteObjects(cp)
      ObjectWillBeMovedEvent dilbert
      ObjectMovedEvent dilbert
      ContainerModifiedEvent folder
      [{'new_id': 'dilbert', 'id': 'dilbert'}]

    And copy::

      >>> cp = folder.manage_copyObjects('dilbert')
      >>> folder.manage_pasteObjects(cp)
      ObjectCopiedEvent copy_of_dilbert
      ObjectWillBeAddedEvent copy_of_dilbert
      ObjectAddedEvent copy_of_dilbert
      ContainerModifiedEvent folder
      ObjectClonedEvent copy_of_dilbert
      [{'new_id': 'copy_of_dilbert', 'id': 'dilbert'}]

    Then rename::

      >>> folder.manage_renameObject('copy_of_dilbert', 'wally')
      ObjectWillBeMovedEvent copy_of_dilbert
      ObjectMovedEvent wally
      ContainerModifiedEvent folder

    Or copy using manage_clone::

      >>> res = folder.manage_clone(folder.dilbert, 'phb')
      ObjectCopiedEvent phb
      ObjectWillBeAddedEvent phb
      ObjectAddedEvent phb
      ContainerModifiedEvent folder
      ObjectClonedEvent phb
      >>> res.getId()
      'phb'

    OrderedFolder's renaming behaviour::

      >>> ofolder = MyOrderedFolder('ofolder')
      >>> app._setObject('ofolder', ofolder)
      ObjectWillBeAddedEvent ofolder
      ObjectAddedEvent ofolder
      ContainerModifiedEvent
      'ofolder'
      >>> ob1 = MyContent('ob1')
      >>> ofolder._setObject('ob1', ob1)
      ObjectWillBeAddedEvent ob1
      ObjectAddedEvent ob1
      ContainerModifiedEvent ofolder
      'ob1'
      >>> ob2 = MyContent('ob2')
      >>> ofolder._setObject('ob2', ob2)
      ObjectWillBeAddedEvent ob2
      ObjectAddedEvent ob2
      ContainerModifiedEvent ofolder
      'ob2'
      >>> ofolder.manage_renameObject('ob1', 'ob4')
      ObjectWillBeMovedEvent ob1
      ObjectMovedEvent ob4
      ContainerModifiedEvent ofolder
      >>> ofolder.objectIds()
      ['ob4', 'ob2']

    When subobjects are reordered, an event about the container is sent::

      >>> ofolder.moveObjectsUp('ob2')
      ContainerModifiedEvent ofolder
      1
      >>> ofolder.objectIds()
      ['ob2', 'ob4']

    Now for a tree of objects. Let's create a simple one::

      >>> subfolder = MyFolder('subfolder')
      >>> folder._setObject('subfolder', subfolder)
      ObjectWillBeAddedEvent subfolder
      ObjectAddedEvent subfolder
      ContainerModifiedEvent folder
      'subfolder'
      >>> subfolder = folder.subfolder
      >>> ob = MyContent('mel')
      >>> subfolder._setObject('mel', ob)
      ObjectWillBeAddedEvent mel
      ObjectAddedEvent mel
      ContainerModifiedEvent subfolder
      'mel'

    Renaming a tree of objects::

      >>> folder.manage_renameObject('subfolder', 'firefly')
      ObjectWillBeMovedEvent subfolder
      ObjectWillBeMovedEvent mel
      ObjectMovedEvent firefly
      ObjectMovedEvent mel
      ContainerModifiedEvent folder

    Cloning a tree of objects::

      >>> res = folder.manage_clone(folder.firefly, 'serenity')
      ObjectCopiedEvent serenity
      ObjectWillBeAddedEvent serenity
      ObjectWillBeAddedEvent mel
      ObjectAddedEvent serenity
      ObjectAddedEvent mel
      ContainerModifiedEvent folder
      ObjectClonedEvent serenity
      ObjectClonedEvent mel
      >>> res.getId()
      'serenity'

    Cleanup::

      >>> setup.eventObserverTearDown()
    """
    return


    """
    This is how to debug subscribers::
      >>> from zope.component import getService
      >>> from zope.component.servicenames import Adapters
      >>> adapters = getService(Adapters)
      >>> print adapters.subscriptions([IItem, IObjectMovedEvent], None)
    """


def test_eventservice_compat():
    """
    Check that the old event service tool receives a redispatch of events
    backward compatibility.

    Create fixtures and test object::

      >>> class FakeEventService(Acquisition.Implicit):
      ...     def notifyCompat(self, event_type, ob, info):
      ...         print 'compat', event_type, ob.getId()
      >>> f = Folder()
      >>> f._setObject('portal_eventservice', FakeEventService())
      'portal_eventservice'
      >>> ob = MyContent('ob').__of__(f)

    Setup observing::

      >>> root = setup.eventObserverSetUp()

    Check redispatch occurs::

      >>> from zope.event import notify
      >>> from zope.app.event.objectevent import ObjectModifiedEvent

      >>> notify(ObjectModifiedEvent(ob))
      compat sys_modify_object ob
      ObjectModifiedEvent ob

    Cleanup::

      >>> setup.eventObserverTearDown()
    """


def test_suite():
    return unittest.TestSuite((
        doctest.DocTestSuite(),
        ))

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
