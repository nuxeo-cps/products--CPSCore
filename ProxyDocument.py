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

from OFS.PropertyManager import PropertyManager

from Products.CMFCore.PortalContent import PortalContent
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl

from Products.NuxCPS3.ProxyBase import ProxyBase
from Products.NuxCPS3.CPSBase import CPSBaseDocument

class ProxyDocument(ProxyBase, CPSBaseDocument):
    """A Proxy document is a loose indirection to a document in a
    repository. It has only convenience method to access that document."""

    meta_type = 'CPS Proxy Document'

    security = ClassSecurityInfo()

    def __init__(self, id, repoid=None, version_infos=None):
        CPSBaseDocument.__init__(self, id)
        ProxyBase.__init__(self, repoid, version_infos)

InitializeClass(ProxyDocument)
