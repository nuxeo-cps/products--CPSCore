# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
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
"""Patch BTreeFolder2
"""

import sys
from Products.BTreeFolder2.BTreeFolder2 import BTreeFolder2
from zLOG import LOG, DEBUG
from ZODB.POSException import ConflictError
from OFS.ObjectManager import BeforeDeleteException


# Fix a problem where ConflictErrors were swallowed.

def _delObject(self, id, dp=1):
    object = self._getOb(id)
    try:
        object.manage_beforeDelete(object, self)
    except BeforeDeleteException, ob:
        raise
    except ConflictError: # Added
        raise             # Added
    except:
        LOG('Zope', ERROR, 'manage_beforeDelete() threw',
            error=sys.exc_info())
    self._delOb(id)

BTreeFolder2._delObject = _delObject
