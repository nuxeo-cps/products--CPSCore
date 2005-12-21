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

class IBeforeCommitSubscriber(Interface):
    """Before commit susbscriber interface definition

    Provides a base interface for before hook definitions
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

class IZODBBeforeCommitHook(IBeforeCommitSubscriber):
    """Before commit subcriber base interface
    """
    
    def addSubscriber(hook, args=(), kws=None, order=0):
        """Register a subscriber to call before the transaction is committed.

        The specified hook function will be called after the transaction's
        commit method has been called, but before the commit process has been
        started.  The hook will be passed the specified positional (`args`)
        and keyword (`kws`) arguments.  `args` is a sequence of positional
        arguments to be passed, defaulting to an empty tuple (no positional
        arguments are passed).  `kws` is a dictionary of keyword argument
        names and values to be passed, or the default None (no keyword
        arguments are passed).

        Multiple hooks can be registered and will be called in the order they
        were registered (first registered, first called), except that
        hooks registered with different `order` arguments are invoked from
        smallest `order` value to largest.  `order` must be an integer,
        and defaults to 0.

        For instance, a hook registered with order=1 will be invoked after
        another hook registered with order=-1 and before another registered
        with order=2, regardless of which was registered first.  When two
        hooks are registered with the same order, the first one registered is
        called first.

        Hooks are called only for a top-level commit.  A subtransaction
        commit or savepoint creation does not call any hooks.  If the
        transaction is aborted, hooks are not called, and are discarded.
        Calling a hook "consumes" its registration too:  hook registrations
        do not persist across transactions.  If it's desired to call the same
        hook on every transaction commit, then addBeforeCommitHook() must be
        called with that hook during every transaction; in such a case
        consider registering a synchronizer object via a TransactionManager's
        registerSynch() method instead.
        """
