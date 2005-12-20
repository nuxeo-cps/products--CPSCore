# (C) Copyright 2005 Nuxeo SAS <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
#         Florent Guillaume <fg@nuxeo.com>
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
"""CPSCore interfaces
"""

from zope.interface import Interface
from zope.interface import Attribute

from zope.app.event.interfaces import IModificationDescription


class ISecurityModificationDescription(IModificationDescription):
    """Modification of an object's security.
    """


class ICPSProxy(Interface):
    """CPS Proxy.
    """
    # XXX TODO


class IBaseManager(Interface):
    """Base Manager definition

    Provides a base interface for before commit hooks definitions
    """

    DEFAULT_SYNC = Attribute('DEFAULT_SYNC', "Default sync mode")
    DEFAULT_STATUS = Attribute('DEFAULT_STATUS', "Default status")

    def setSynchronous(sync):
        """Set queuing mode.
        """

    def isSynchronous():
        """Get queuing mode.
        """

    def __call__():
        """Called when transaction commits.

        Does the actual manager work.
        """

    def enable():
        """Enable the manager
        """

    def disable():
        """Disable the manager
        """
