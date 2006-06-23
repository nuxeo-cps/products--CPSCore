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
import zope.schema
from zope.configuration.fields import GlobalObject

from zope.app.event.interfaces import IModificationDescription
from OFS.interfaces import IPropertyManager



class IUpgradeStepDirective(Interface):
    """Register an upgrade setup.
    """
    title = zope.schema.TextLine(
        title=u"Title",
        required=True)

    category = zope.schema.ASCII(
        title=u"Category",
        required=False)

    source = zope.schema.ASCII(
        title=u"Source version",
        required=False)

    destination = zope.schema.ASCII(
        title=u"Destination version",
        required=False)

    sortkey = zope.schema.Int(
        title=u"Sort key",
        required=False)

    handler = GlobalObject(
        title=u"Upgrade handler",
        required=True)

    checker = GlobalObject(
        title=u"Upgrade checker",
        required=False)


class ISecurityModificationDescription(IModificationDescription):
    """Modification of an object's security.
    """

class ICPSSite(Interface):
    """CPS Site.
    """

class ICPSProxy(Interface):
    """CPS Proxy.
    """
    # XXX TODO

class ITreeTool(Interface):
    """Tree Tool.
    """

class ITreeCache(Interface):
    """Tree Cache.
    """

class IEventServiceTool(Interface):
    """Event Service Tool.
    """

class IEventSubscriber(IPropertyManager):
    """Event Subscriber.
    """


class ICommitSubscriber(Interface):
    """Base interface for before commits
    """

    DEFAULT_SYNC = Attribute('DEFAULT_SYNC', "Default sync mode")
    enabled = Attribute('enabled', "Default is True")

    def setSynchronous(sync):
        """Set queuing mode.
        """

    def isSynchronous():
        """Get queuing mode.
        """

    def enable():
        """Enable the manager
        """

    def disable():
        """Disable the manager
        """

class IBeforeCommitSubscriber(ICommitSubscriber):
    """Before commit susbscriber interface definition

    Provides a marker insterface for before hook definitions
    """

    def __call__():
        """ Do the actual job
        """

class IAfterCommitSubscriber(ICommitSubscriber):
    """Base After Commit Subscriber interface definition

    Provides a marker inteface for after commit subscriber
    """

    def __call__(status=True):
        """Do the actual job

        Status is the status of the transaction commit.

        true if succeded or false of aborted (or not done for use in
        CPS if we use sync mode.)
        """
        raise NotImplementedError

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

class IZODBAfterCommitHook(IAfterCommitSubscriber):
    """After commit subcriber base interface
    """

    def addSubscriber(subscriber, args=(), kws=None, order=0):
        """Register a subscriber to call after a transaction commit attempt.

         The specified subscriber function will be called after the
         transaction commit succeeds or aborts.  The first argument
         passed to the subscriber is a Boolean value, true if the
         commit succeeded, or false if the commit aborted.  `args`
         specifies additional positional, and `kws` keyword, arguments
         to pass to the subscriber.  `args` is a sequence of
         positional arguments to be passed, defaulting to an empty
         tuple (only the true/false success argument is passed).
         `kws` is a dictionary of keyword argument names and values to
         be passed, or the default None (no keyword arguments are
         passed).

         Multiple subscribers can be registered and will be called in
         the order they were registered (first registered, first
         called). except that hooks registered with different `order`
         arguments are invoked from smallest `order` value to largest.
         `order` must be an integer, and defaults to 0.

         For instance, a hook registered with order=1 will be invoked
         after another hook registered with order=-1 and before
         another registered with order=2, regardless of which was
         registered first.  When two hooks are registered with the
         same order, the first one registered is called first.

         This method can also be called from a subscriber:
         an executing subscriber can register more subscribers.
         Applications should take care to avoid creating infinite
         loops by recursively registering subscribers.

         Subscribers are called only for a top-level commit.  A
         subtransaction commit or savepoint creation does not call any
         subscribers.  Calling a subscriber"consumes" its registration:
         subscriber registrations do not persist across transactions.

         If it's desired to call the same subscriber on every
         transaction commit, then addSubscriber() must be called with
         that subscriber during every transaction; in such a case
         consider registering a synchronizer object via a
         TransactionManager's registerSynch() method instead.
         """
