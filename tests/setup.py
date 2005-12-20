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
"""Various setups for unit tests.
"""

from time import time
import unittest
import ZODB.tests.util
from zope.component import getGlobalServices
from zope.component.exceptions import ComponentLookupError
from zope.app.testing import ztapi
from zope.app.testing import placelesssetup
from Products.Five import zcml

import transaction

from zope.app.event.interfaces import IObjectEvent
from zope.app.container.interfaces import IObjectMovedEvent
from OFS.interfaces import IObjectWillBeMovedEvent
from OFS.interfaces import IObjectClonedEvent
from OFS.interfaces import IItem

class EventTest(placelesssetup.PlacelessSetup):

    _zcml = None

    def prepareZcml(self):
        if self._zcml is not None:
            return
        from zope.configuration.xmlconfig import file
        import Products.Five
        import Products.CPSCore
        zcml = file('meta.zcml', Products.Five, execute=False)
        #file('i18n.zcml', Products.Five, execute=False, context=zcml)
        #file('permissions.zcml', Products.Five, execute=False, context=zcml)
        file('event.zcml', Products.Five, execute=False, context=zcml)
        file('deprecated.zcml', Products.Five, execute=False, context=zcml)
        #file('configure.zcml', Products.CMFCore, execute=False, context=zcml)
        file('configure.zcml', Products.CPSCore, execute=False, context=zcml)
        self._zcml = zcml

    def beforeLoadZcml(self):
        pass

    def executeZcml(self):
        self._zcml.execute_actions(clear=False)

    def loadZcml(self):
        self.prepareZcml()
        self.executeZcml()

    def setUp(self):
        super(EventTest, self).setUp()
        self.beforeLoadZcml()
        self.loadZcml()

    def tearDown(self):
        super(EventTest, self).tearDown()


_eventTest = EventTest()
eventSetUp = _eventTest.setUp
eventTearDown = _eventTest.tearDown


def fullFiveSetup():
    from Products.Five import zcml
    # Cleanup everything first
    placelesssetup.tearDown()
    # Now reload Five setup
    zcml._initialized = False
    zcml.load_site()


class EventObserverTest(EventTest):

    _db = None
    _connection = None

    def setUp(self):
        super(EventObserverTest, self).setUp()

        # Work inside a database
        self._db = ZODB.tests.util.DB()
        self._connection = self._db.open()
        self.root = self._connection.root()
        return self.root

    def tearDown(self):
        transaction.abort()
        if self._connection is not None:
            self._connection.close()
        if self._db is not None:
            self._db.close()

        super(EventObserverTest, self).tearDown()

    def beforeLoadZcml(self):
        # Add some event observers. We do this before load the zcml
        # config, as it's going to add further event subscribers and we
        # want our testing prints to be first.
        ztapi.subscribe((IItem, IObjectMovedEvent), None,
                        self.printObjectEvent)
        ztapi.subscribe((IItem, IObjectWillBeMovedEvent), None,
                        self.printObjectEvent)
        ztapi.subscribe((IItem, IObjectClonedEvent), None,
                        self.printObjectEvent)
        ztapi.subscribe((None, IObjectEvent), None,
                        self.printObjectEventExceptSome)

    def printObjectEvent(self, object, event):
        info = '%s %s' % (event.__class__.__name__, object.getId())
        # We strip to avoid having to say NORMALIZE_WHITESPACE in doctests
        print info.strip()

    def printObjectEventExceptSome(self, object, event):
        if (IObjectMovedEvent.providedBy(event) or
            IObjectWillBeMovedEvent.providedBy(event) or
            IObjectClonedEvent.providedBy(event)):
            return
        self.printObjectEvent(object, event)


_eventObserverTest = EventObserverTest()
eventObserverSetUp = _eventObserverTest.setUp
eventObserverTearDown = _eventObserverTest.tearDown
