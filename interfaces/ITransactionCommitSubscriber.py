# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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

"""Transaction commit subscriber interface

See CPSCore/TransactionCommitSubscribers for implementation
See CPSCore/PatchZODB for the Transaction extensions
"""

import Interface

class ITransactionCommitSubscriber(Interface.Base):
    """Transaction commit subscriber interface
    """

    def register():
        """Register self as before transaction commit subscriber
        """

    def commit(transaction):
        """Execute what's need to be done before the first transaction
        commit phase
        """

    def abort(transaction):
        """Code to be executed when the transaction is aborded

        Should never fail !!
        """

    def push(ob, **kw):
        """Add an object within the subscriber queue.

        **kw has to be handled within a subscriber dedicated data structure
        """
