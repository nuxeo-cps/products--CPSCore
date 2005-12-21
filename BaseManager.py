# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Anguenot <ja@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
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
"""Base Manager.

Provides a base class for before commit hooks definitions
"""

import zope.interface

from Products.CPSCore.interfaces import IBaseManager

class BaseManager(object):
    """Base Manager definition
    """

    zope.interface.implements(IBaseManager)

    # Not synchronous by default
    # XXX This may be monkey-patched by unit-tests.
    DEFAULT_SYNC = False

    # Enabled by default
    DEFAULT_STATUS = True

    def __init__(self, mgr, order=0):
        self._sync = self.DEFAULT_SYNC
        self._status = self.DEFAULT_STATUS
        mgr.addSubscriber(self, order=order)

    def setSynchronous(self, sync):
        """Set queuing mode."""
        if sync:
            self()
        self._sync = sync

    def isSynchronous(self):
        """Get queuing mode."""
        return self._sync

    def __call__(self):
        raise NotImplementedError

    def push(self, *args):
        raise NotImplementedError

    def enable(self):
        self._status = True

    def disable(self):
        self._status = False

