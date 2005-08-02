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

from Products.CMFCore.permissions import View
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces.portal_url import portal_url as IURLTool
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.URLTool import URLTool as CMFURLTool
from Products.CMFCore.ActionProviderBase import ActionProviderBase

from Products.CPSUtil.text import truncateText

class URLTool(CMFURLTool, SimpleItemWithProperties):
    """ CPS URL Tool.
    """

    __implements__ = (IURLTool, ActionProviderBase.__implements__)

    id = 'portal_url'
    meta_type = 'CPS URL Tool'

    _actions = ()

    _properties = (
        {'id': 'breadcrumbs_show_root', 'type': 'boolean', 'mode': 'w',
         'label': 'Show portal (or virtual root) in breadcrumbs'},
        {'id': 'breadcrumbs_root_name', 'type': 'string', 'mode': 'w',
         'label': "Root of breadcrumbs i18n name"},
        # Do not show invisible items in breadcrumbs, or show them without a
        # link on their name.
        {'id': 'breadcrumbs_show_invisible', 'type': 'boolean', 'mode': 'w',
         'label': 'Show invisible items in breadcrumbs'},
        )
    breadcrumbs_show_root = True
    breadcrumbs_root_name = ''
    breadcrumbs_show_invisible = False

    security = ClassSecurityInfo()

    manage_options = (ActionProviderBase.manage_options
                      + ({'label':'Overview',
                          'action':'manage_overview',},
                         )
                      + SimpleItemWithProperties.manage_options
                      )

    security.declarePublic('getRpath')
    def getRpath(self, content):
        """ Get the path for an object, relative to the portal root.

        Provides an alias name for the CMF URLTool getRelativeContentURL
        method.
        """
        return self.getRelativeContentURL(content)

    security.declarePublic("getBaseUrl")
    def getBaseUrl(self):
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

    security.declarePublic("getRpathFromPath")
    def getRpathFromPath(self, path):
        """Get the object relative path from its physical path

        path can either be a tuple like ('', 'foo', 'bar') or a string like
        '/foo/bar'.
        """
        portal_path = self.getPortalObject().getPhysicalPath()
        if isinstance(path, str):
            path = path.split('/')
        rpath = path[len(portal_path):]
        rpath = '/'.join(rpath)
        return rpath

    security.declarePublic("getUrlFromRpath")
    def getUrlFromRpath(self, rpath):
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

        # add virtual root
        if self.breadcrumbs_show_root:
            if len(parents) == 0 or parents[-1] != vr:
                parents.append(vr)

        parents.reverse()

        return parents

    security.declarePublic("getBreadCrumbsInfo")
    def getBreadCrumbsInfo(self, context=None, only_parents=0, title_size=20):
        """
        Title is truncated so that its size is 20 characters (middle truncture)
        """
        parents = self.getBreadCrumbs(context, only_parents)
        items = []
        first_loop = 1
        for obj in parents:
            visible = _checkPermission(View, obj)
            if visible or self.breadcrumbs_show_invisible:
                # title
                if (first_loop
                    and self.breadcrumbs_show_root
                    and self.breadcrumbs_root_name):
                    mcat = getToolByName(self, 'translation_service')
                    title = mcat(self.breadcrumbs_root_name,
                                 default=self.breadcrumbs_root_name)
                else:
                    title = obj.title_or_id()
                    try:
                        is_archived = obj.isProxyArchived()
                    except AttributeError:
                        is_archived = 0
                    if is_archived:
                        # XXX i18n
                        title = 'v%s (%s)' % (obj.getRevision(), title)
                # url, rpath
                if not visible:
                    url = ''
                    rpath = ''
                else:
                    url = obj.absolute_url()
                    rpath = self.getRpath(obj)
                items.append({'id': obj.getId(),
                              'title': truncateText(title, size=title_size),
                              'longtitle': title,
                              'url': url,
                              'rpath': rpath,
                              })
            first_loop = 0
        return items

InitializeClass(URLTool)
