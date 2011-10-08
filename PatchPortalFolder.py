# (C) Copyright 2010 Association Paris-Montagne
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

"""This patch provides support for HEAD in PortalFolder

It would be more logical to do this at the level of PortalContent, but:
  - PortalFolder is before PortalContent in the inheritance hierarchy of
  CPSBaseDocument.
  - webdav.Collection comes with PortalFolder
"""

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Acquisition import aq_base

from Products.CMFCore.PortalFolder import PortalFolder
from Products.CMFCore.permissions import View

from interfaces import ICPSSite

security = ClassSecurityInfo()

security.declareProtected(View, 'HEAD')
def HEAD(self):
    """Provide support for HEAD

    Otherwise, the default webdav.Collection is called, and it expects
    the rendering to be done by a 'index_html' object with a HEAD method,
    but CMF PortalContent sets index_html to None to trigger the use of
    __call__
    """
    # don't know how to avoid doing the rendering to know the length
    # This is mostly based on PortalContent.__call__
    # had to duplicate to set properly PUBLISHED (needed for portlets guard)
    # trying to reset it (from HEAD to None, deleting...) did not work

    ti = self.getTypeInfo()
    method_id = ti and ti.queryMethodID('(Default)', context=self)
    if method_id and method_id!='(Default)':
        method = getattr(self, method_id)
    elif ICPSSite.providedBy(self):
        method = self.index_html
    else:
        logger.error('No (Default) alias defined for %r (ti=%r)', self, ti)
        method = lambda : ''

    req = self.REQUEST
    resp = req.RESPONSE

    req['PUBLISHED'] = method # here the specific part

    if getattr(aq_base(method), 'isDocTemp', 0):
        body = method(self, req, resp)
    else:
        body = method()

    resp.setHeader('Content-Length', len(body))


PortalFolder.security = security
PortalFolder.HEAD = HEAD
InitializeClass(PortalFolder)
