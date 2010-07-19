# (C) Copyright 2010 Georges Racinet
# Author: Georges Racinet <georges@racinet.fr>
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

from Products.GenericSetup.context import BaseContext

"""Patches of GenericSetup

- work around the fact that the default encoding is 'no encoding',
 leading to 'ascii' encoding, that breaks snapshots with unicode content,
 whereas the default XML encoding is utf-8
 Of course, this could be done at the level of CPS' subclass, but it's simpler
 and safer  to do it once and for all here.
"""

def getEncoding(self):
    enc = self._encoding
    return enc is not None and enc or 'utf-8'

BaseContext.getEncoding = getEncoding
