# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""This file contains all patches for the CMFDefault product."""

from zLOG import LOG, DEBUG, INFO


#------------------------------------------------------------
# This patch submitted by efge fixes CMFDefault bug
# http://www.zope.org/Collectors/CMF/300
#
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl

LOG('PatchCMFDefault.DefaultDublinCoreImpl', INFO,
    'CPSCore Patching Creator CMFDefault bug #300')

def cmf_Creator(self):
    """Dublin Core element - resource creator

    using efge patch to prevent http://www.zope.org/Collectors/CMF/300/
    """
    # XXX: fixme using 'portal_membership' -- should iterate over
    #       *all* owners
    owner_tuple = self.getOwnerTuple()
    if owner_tuple[0] is None:
        return 'No owner'
    return owner_tuple[1]
DefaultDublinCoreImpl.Creator = cmf_Creator

LOG('PatchCMFDefault.DefaultDublinCoreImpl', DEBUG, 'Patched')


