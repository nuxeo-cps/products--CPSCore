# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
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

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFCore.PortalContent import PortalContent

from Products.NuxCPS3.ProxyBase import ProxyBase


ProxyDocument_meta_type = 'CPS Document Proxy'

class ProxyDocument(ProxyBase, PortalContent):
    """A Proxy document is a loose indirection to a document in a
    repository. It has only convenience method to access that document."""

    meta_type = ProxyDocument_meta_type

    security = ClassSecurityInfo()

    def __init__(self, portal_type, repoid=None, version_filter=None):
        PortalContent.__init__(self)
        ProxyBase.__init__(self, repoid, version_filter)




InitializeClass(ProxyDocument)
