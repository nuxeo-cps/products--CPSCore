# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Trees Tool, that caches some information about the site's hierarchies.
"""

from zLOG import LOG, DEBUG
from types import DictType
from copy import deepcopy
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo

from OFS.Folder import Folder

from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ManagePortal
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import UniqueObject, getToolByName


class TreesTool(UniqueObject, Folder):
    """Trees Tool that caches information about the site's hierarchies.
    """

    id = 'portal_trees'
    meta_type = 'CPS Trees Tool'

    security = ClassSecurityInfo()

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, object, infos):
        LOG('TreesTool', DEBUG, 'Got %s for %s'
            % (event_type, '/'.join(object.getPhysicalPath())))
        if event_type not in ('sys_add_cmf_object',
                              'sys_clone_object',
                              'sys_del_object',
                              'modify_object'):
            return
        if not object.isPrincipiaFolderish:
            return
        id = object.getId()
        LOG('TreesTool', DEBUG, 'Notifying...')
        for tree in self.objectValues():
            tree.notify(event_type, object, infos)

    #
    # ZMI
    #

    def all_meta_types(self):
        return ({'name': 'CPS Tree Cache',
                 'action': 'manage_addCPSTreeCacheForm',
                 'permission': ManagePortal},)

##     manage_options = (
##         {'label': 'Trees',
##          'action': 'manage_listTrees',
##          },
##         ) + Folder.manage_options[1:]

##     security.declareProtected(ViewManagementScreens, 'manage_listTrees')
##     manage_listTrees = DTMLFile('zmi/trees_content', globals())

    security.declareProtected(ViewManagementScreens, 'manage_addCPSTreeCacheForm')
    manage_addCPSTreeCacheForm = DTMLFile('zmi/tree_add', globals())

    security.declareProtected(ViewManagementScreens, 'manage_addCPSTreeCache')
    def manage_addCPSTreeCache(self, id, REQUEST=None):
        """Add a tree cache."""
        ob = TreeCache(id)
        id = ob.getId()
        self._setObject(id, ob)
        ob = self._getOb(id)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(ob.absolute_url()+'/manage_workspace')

InitializeClass(TreesTool)


class TreeCache(SimpleItemWithProperties):
    """Tree cache object, caches information about one hierarchy.
    """
    meta_type = 'CPS Tree Cache'

    security = ClassSecurityInfo()
    security.declareObjectProtected(View)

    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w',
         'label': 'Title'},
        {'id': 'root', 'type': 'string', 'mode': 'w',
         'label': 'Root'},
        {'id': 'type_names', 'type': 'multiple selection', 'mode': 'w',
         'select_variable': 'all_type_names', 'label': 'Portal Types'},
        {'id': 'meta_types', 'type': 'lines', 'mode': 'w',
         'label': 'Meta Types'},
        {'id': 'info_method', 'type': 'string', 'mode': 'w',
         'label': 'Info Method'},
        )
    title = ''
    root = ''
    type_names = []
    meta_types = ('CPS Proxy Folder',)
    info_method = ''

    def __init__(self, id, **kw):
        self._setId(id)
        self._tree = {} # XXX use PersistentMapping here, in init()
        self._list = [] # XXX use PersistentList...

    security.declareProtected(ViewManagementScreens, 'all_type_names')
    def all_type_names(self):
        """Return the allowed type names."""
        res = []
        ttool = getToolByName(self, 'portal_types')
        for ti in ttool.listTypeInfo():
            id = ti.getId()
            if id not in ('CPS Proxy Folder', 'CPS Proxy Document'):
                res.append(id)
        res.sort()
        return res

    security.declarePrivate('notify')
    def notify(self, event_type, object, infos):
        """Hook called when the tree changes."""
        portal = getToolByName(self, 'portal_url').getPortalObject()
        plen = len(portal.getPhysicalPath())
        if self._is_candidate(object, plen):
            LOG('Tree', DEBUG, 'ob is candidate, rebuilding.')
            self.rebuild()

    security.declarePrivate('rebuild')
    def rebuild(self):
        """Rebuild all the tree."""
        urltool = getToolByName(self, 'portal_url')
        hubtool = getToolByName(self, 'portal_eventservice')
        portal = urltool.getPortalObject()
        plen = len(portal.getPhysicalPath())
        info_method = self.info_method.strip()
        self._sanitize()
        if self.root:
            ob = portal.unrestrictedTraverse(self.root)
        else:
            ob = portal
        tree = self._rebuild(ob, 0, plen, info_method, hubtool)
        self._tree = tree
        # Compute list
        flat = [] # XXX persistentlist
        self._flatten(tree, flat)
        self._list = flat

    def _sanitize(self):
        if self.root != self.root.strip():
            self.root = self.root.strip()

    def _is_candidate(self, ob, plen):
        """Return True if the object should be cached."""
        LOG('Tree', DEBUG, 'Is %s candidate?' % ob.getId())
        if ob.meta_type not in self.meta_types:
            LOG('Tree', DEBUG, ' No, mt=%s' % ob.meta_type)
            return 0
        if getattr(ob, 'portal_type', None) not in self.type_names:
            LOG('Tree', DEBUG, ' No, pt=%s' % ob.portal_type)
            return 0
        root = self.root
        if not root:
            return 1
        rloc = ob.getPhysicalPath()[plen:]
        rpath = '/'.join(rloc)
        ok = rpath.startswith(root)
        LOG('Tree', DEBUG, ' Returns ok=%s' % ok)
        return ok

    def _get_one(self, ob, plen, info_method, hubtool, hubid=None):
        """Get info on one object."""
        res = {} # XXX use PersistentMapping here
        if info_method:
            method = getattr(ob, info_method, None)
            if method is not None:
                r = method()
                if isinstance(r, DictType):
                    res = r
                else:
                    LOG('TreeCache', ERROR, '_get_one returned non-dict %s'
                        % `r`)
        if hubid is None:
            hubid = hubtool.getHubId(ob)
        ppath = ob.getPhysicalPath()
        res.update({'id': ob.getId(),
                    'url': ob.absolute_url(),
                    'path': '/'.join(ppath),
                    'rpath': '/'.join(ppath[plen:]),
                    'hubid': hubid,
                    })
        # XXX compute ~allowedRolesAndUsers too
        return res

    def _rebuild(self, ob, depth, plen, info_method, hubtool):
        """Rebuild, starting at ob."""
        res = self._get_one(ob, plen, info_method, hubtool)
        res['depth'] = depth
        children = [] # XXX persistentlist
        for subob in ob.objectValues():
            if self._is_candidate(subob, plen):
                children.append(self._rebuild(subob, depth+1,
                                              plen, info_method, hubtool))
        res['children'] = children
        return res

    def _flatten(self, info, res):
        """Flatten the informations."""
        d = info.copy()
        res.append(d)
        if d.has_key('children'):
            del d['children']
            for subinfo in info['children']:
                self._flatten(subinfo, res)

    #
    # API
    #

    security.declareProtected(ViewManagementScreens, 'manage_rebuild')
    def manage_rebuild(self, REQUEST=None):
        """Rebuild all the tree."""
        self.rebuild()
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url()+'/manage_listTree')

    security.declareProtected(View, 'getTree')
    def getTree(self):
        """Return the cached tree."""
        return deepcopy(self._tree)

    security.declareProtected(View, 'getList')
    def getList(self):
        """Return the cached tree as a list."""
        return deepcopy(self._list)

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Tree',
         'action': 'manage_listTree',
         },
        ) + SimpleItemWithProperties.manage_options

    security.declareProtected(ViewManagementScreens, 'manage_listTree')
    manage_listTree = DTMLFile('zmi/tree_content', globals())
