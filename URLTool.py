# -*- coding: iso-8859-15 -*-
# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
# Author: Anahide Tchertchian <at@nuxeo.com>
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
"""
Url Tool to add methods to the CMF url tool

- deal with virtual hosting
"""

from zLOG import LOG, DEBUG

from AccessControl import ClassSecurityInfo
from AccessControl import Unauthorized
from Acquisition import aq_inner
from Acquisition import aq_parent
from Globals import InitializeClass

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.URLTool import URLTool as CMFURLTool
from Products.CMFCore.interfaces.portal_url import portal_url as IURLTool
from Products.CMFCore.ActionProviderBase import ActionProviderBase

from Products.CPSUtil.text import truncateText

class URLTool(CMFURLTool):
    """ CPS URL Tool.
    """

    __implements__ = (IURLTool, ActionProviderBase.__implements__)

    id = 'portal_url'
    meta_type = 'CPS URL Tool'
    _actions = ()

    security = ClassSecurityInfo()

    security.declarePublic('getRpath')
    def getRpath(self, content):
        """ Get the path for an object, relative to the portal root.

        Provides an alias name for the CMF URLTool getRelativeContentURL
        method.
        """
        return self.getRelativeContentURL(content)

    security.declarePublic("getBaseURL")
    def getBaseURL(self):
        """Get base url for the portal; handles virtual hosting
        """
        portal = self.getPortalObject()
        base_url = portal.absolute_url_path()
        if not base_url.endswith('/'):
            base_url += '/'
        return base_url

    security.declarePrivate("getVirtualRootPhysicalPath")
    def getVirtualRootPhysicalPath(self):
        """Get the virtual root physical path

        Can be ('',), ('', 'portal'), etc...
        """
        vr = None
        if self.REQUEST is not None:
            vr = self.REQUEST.get('VirtualRootPhysicalPath')
        if vr is None:
            vr = ('',)
        return vr

    security.declarePrivate("getVirtualHostPhysicalPath")
    def getVirtualHostPhysicalPath(self):
        """Get the virtual host physical path

        Can be ('',), ('', 'foo'), ('', 'foo', 'bar'), etc...
        """
        app = self.getPhysicalRoot()
        aup = app.absolute_url_path()
        if aup == '/':
            path = ('',)
        else:
            path = tuple(aup.split('/'))
        return path

    security.declarePublic("getURLFromRpath")
    def getURLFromRpath(self, rpath):
        """Guess the object absolute url from the relative url
        """
        path = rpath.split('/')

        # add portal path
        portal = self.getPortalObject()
        portal_path = portal.getPhysicalPath()
        path[0:0] = portal_path

        # remove virtual root
        vr = list(self.getVirtualRootPhysicalPath())
        path = path[len(vr):]

        # add root absolute url (takes care of virtual hosts)
        root_url = self.getPhysicalRoot().absolute_url()
        url = root_url + '/' + '/'.join(path)

        # avoid calling costly restrictedTraverse
        #portal = self.getPortalObject()
        #ob = portal.restrictedTraverse(rpath, None)
        #if ob is not None:
        #    url = ob.absolute_url()
        #else:
        #    url = ''
        return url

    security.declarePublic("getBreadCrumbs")
    def getBreadCrumbs(self, context=None, only_parents=0):
        """Return parents for context

        If only_parents is set to 1, the object itself is not returned in bread
        crumbs.
        """
        root = self.getPhysicalRoot()
        portal = self.getPortalObject()
        if context is None:
            context = portal

        vrpath = '/'.join(self.getVirtualRootPhysicalPath())
        if vrpath:
            vr = portal.restrictedTraverse(vrpath)
        else:
            vr = portal

        if only_parents or context in (vr, portal, root):
            parents = []
        else:
            parents = [context]

        current = context
        while 1:
            parent = aq_parent(aq_inner(current))
            if parent not in (vr, portal, root):
                parents.append(parent)
                current = parent
            else:
                break

        # add portal as root if not here
        if len(parents) == 0 or parents[-1] != portal:
            parents.append(portal)

        parents.reverse()

        return parents

    security.declarePublic("getBreadCrumbsInfo")
    def getBreadCrumbsInfo(self, context=None, only_parents=0, title_size=20):
        """
        Title is truncated so that its size is 20 characters (middle truncture)
        """
        parents = self.getBreadCrumbs(context, only_parents)
        items = []
        for obj in parents:
            title = obj.title_or_id()
            try:
                is_archived = obj.isProxyArchived()
            except AttributeError:
                is_archived = 0
            if is_archived:
                # XXX i18n
                title = 'v%s (%s)' % (obj.getRevision(), title)
            aup = obj.absolute_url_path()
            url = '%s/' % aup
            items.append({'id': obj.getId(),
                          'title': truncateText(title, size=title_size),
                          'longtitle': title,
                          'url': url,
                          'rpath': aup,
                         })
        return items

InitializeClass(URLTool)
