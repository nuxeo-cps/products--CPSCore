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

"""Base ZODB Hook interface

Inspired by http://cvs.plope.com/viewcvs/Products/blob/
"""

import Interface

class IZODBTransactionHook(Interface.Base):

    def commit(reallyme, t):
        """ Called for every (sub-)transaction commit """
        pass

    def tpc_begin(transaction, subtransaction=None):
        """ Called at the beginning of a transaction """
        pass

    def tpc_abort(transaction):
        """ Called on abort - but not always :( """
        pass

    def abort(reallyme, t):
        """ Called if the transaction has been aborted """
        pass
    
    def tpc_vote(transaction):
        """Call at the end of a real transaction only
        """
        pass

    def tpc_finish(transaction):
        """ Called at the end of a successful transaction """
        pass

    def sortKey(*ignored):
        """ The sortKey method is used for recent ZODB compatibility which
            needs to have a known commit order for lock acquisition.  We use
            our timestamp, which will ensure that the order in which file
            cache entries are created will be the way the operations they
            imply are played back.
        """
        pass
