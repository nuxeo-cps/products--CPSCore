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

from zLOG import LOG, DEBUG, ERROR
from types import DictType
from Globals import InitializeClass, DTMLFile
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from ZODB.PersistentMapping import PersistentMapping
from ZODB.PersistentList import PersistentList

from OFS.Folder import Folder

from Products.CMFCore.CMFCorePermissions \
    import View, ManagePortal, ViewManagementScreens
from Products.CMFCore.utils \
    import SimpleItemWithProperties, UniqueObject, getToolByName

from Products.CPSCore.utils \
    import _allowedRolesAndUsers, _getAllowedRolesAndUsers


class TreesTool(UniqueObject, Folder):
    """Trees Tool that caches information about the site's hierarchies.
    """

    id = 'portal_trees'
    meta_type = 'CPS Trees Tool'

    security = ClassSecurityInfo()

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, object, infos):
        # XXX: Docstring ?
        if event_type not in ('sys_add_cmf_object', # XXX ugh clean this up
                              'sys_del_object',
                              'sys_modify_object',
                              'sys_modify_security',
                              'sys_order_object',
                              'modify_object'):
            return
        LOG('TreesTool', DEBUG, 'Got %s for %s'
            % (event_type, '/'.join(object.getPhysicalPath())))
        if not object.isPrincipiaFolderish:
            return
        for tree in self.objectValues():
            tree.notify_tree(event_type, object, infos)

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
    meta_types = ('CPS Proxy Folder', 'CPS Proxy Folderish Document',)
    info_method = ''

    def __init__(self, id, **kw):
        self._setId(id)
        self._clear()

    def _new_tree(self, d={}):
        return PersistentMapping(d)

    def _clear(self):
        self._tree = self._new_tree() # The full tree.
        self._pointers = []           # A list of subtrees.
        self._flat = []               # A list of tree nodes only.

    security.declareProtected(ViewManagementScreens, 'all_type_names')
    def all_type_names(self):
        """Return the allowed type names."""
        res = []
        ttool = getToolByName(self, 'portal_types')
        for ti in ttool.listTypeInfo():
            id = ti.getId()
            if id not in ('CPS Proxy Folder', 'CPS Proxy Document', 
                          'CPS Proxy Folderish Document',):
                res.append(id)
        res.sort()
        return res

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, object, infos):
        """Hook called when the tree changes."""
        LOG('TreeCache.notify_tree', DEBUG, 'Event %s for %s'
            % (event_type, '/'.join(object.getPhysicalPath())))
        urltool = getToolByName(self, 'portal_url')
        portal = urltool.getPortalObject()
        plen = len(portal.getPhysicalPath())
        rebuild = 0
        if event_type == 'sys_add_cmf_object':
            if not self._is_candidate(object, plen):
                return
            # New object.
            container = aq_parent(aq_inner(object))
            tree = self._find_tree(container)
            if tree is None:
                # Container not found, but object may be the new root...
                root = self.root
                if root.endswith('/'):
                    root = root[:-1]
                rpath = urltool.getRelativeUrl(object) # XXX use infos
                if rpath != root:
                    return
                LOG('TreeCache.notify_tree', DEBUG,
                    'Added a new root %s' % root)
                self.rebuild()
                return
            LOG('TreeCache.notify_tree', DEBUG, '  Adding object')
            # XXX Here we have to be careful not to readd something
            # we already have, which can happen for a rename: we
            # have already received the sys_order_object event
            # and thus fully recomputed the children.
            subtree = self._get_tree(object, tree['depth']+1)
            id = object.getId()
            for child in tree['children']:
                if child['id'] == id:
                    LOG('TreeCache.notify_tree', DEBUG,
                        '   Aha, already there')
                    # Already there.
                    return
            # XXX adds at end... should find from container order.
            tree['children'].append(subtree)
            rebuild = 1
        elif event_type == 'sys_del_object':
            # Deleted object.
            container = aq_parent(aq_inner(object))
            tree = self._find_tree(container)
            if tree is None:
                # Container not found, but object may be the root...
                root = self.root
                if root.endswith('/'):
                    root = root[:-1]
                rpath = urltool.getRelativeUrl(object)
                if rpath != root:
                    return
                LOG('TreeCache.notify_tree', DEBUG, 'Deleting root %s' % root)
                self._clear()
                return
            id = object.getId()
            children = tree['children']
            for i in range(len(children)):
                if children[i]['id'] == id:
                    LOG('TreeCache.notify_tree', DEBUG, '  Del pos %s' % i)
                    children.pop(i)
                    rebuild = 1
                    break
        elif event_type == 'sys_order_object':
            container = object
            tree = self._find_tree(container)
            if tree is None:
                return
            # XXX We recompute the whole subtree, we could be more intelligent
            depth = tree['depth']
            children = self._get_children(container, depth+1, plen)
            tree['children'] = children
            rebuild = 1
        else: # event_type in ('sys_modify_security', 'modify_object')
            tree = self._find_tree(object)
            if tree is None:
                return
            info = self._get_info(object, plen)
            LOG('TreeCache.notify_tree', DEBUG, '  Updating info %s' % `info`)
            # Ensure script-provided data doesn't conflict.
            for k in ('depth', 'children'):
                if info.has_key(k):
                    del info[k]
            tree.update(info)
            rebuild = 1
        if rebuild:
            self._finish_rebuild()


    def _find_tree(self, ob):
        """Find the tree entry for the object."""
        # XXX don't recompute this
        portal = getToolByName(self, 'portal_url').getPortalObject()
        plen = len(portal.getPhysicalPath())
        if self.root and self.root.find('..') < 0 and self.root[:1] != '/':
            # '..': ensure we don't go outside the portal
            # '/': same
            root = portal.unrestrictedTraverse(self.root, default=None)
            if root is None:
                return None
        else:
            root = portal
        rpath = '/'.join(ob.getPhysicalPath()[plen:])
        tree = None
        for info in self._pointers:
            # XXX _pointers could even be a dict...
            if info['rpath'] == rpath:
                tree = info
                break
        return tree


    security.declarePrivate('rebuild')
    def rebuild(self):
        """Rebuild all the tree."""
        portal = getToolByName(self, 'portal_url').getPortalObject()
        if self.root and self.root.find('..') < 0:
            # '..': ensure we don't go outside the portal
            root = portal.unrestrictedTraverse(self.root, default=None)
            if root is None:
                self._clear()
                return
        else:
            root = portal
        LOG('rebuild', DEBUG, 'Rebuilding from %s'
            % '/'.join(root.getPhysicalPath()))
        self._tree = self._get_tree(root, 0)
        self._finish_rebuild()

    def _is_candidate(self, ob, plen):
        """Return True if the object should be cached."""
        LOG('Tree', DEBUG, 'Is %s candidate?' % ob.getId())
        bob = aq_base(ob)
        if getattr(bob, 'meta_type', None) not in self.meta_types:
            LOG('Tree', DEBUG, ' No, mt=%s' % getattr(bob, 'meta_type', None))
            return 0
        type_names = self.type_names or [] # Stupid, may be ''.
        if getattr(bob, 'portal_type', None) not in type_names:
            LOG('Tree', DEBUG, ' No, pt=%s' % getattr(bob, 'portal_type', None))
            return 0
        root = self.root
        if not root:
            return 1
        rpath = '/'.join(ob.getPhysicalPath()[plen:])
        ok = rpath.startswith(root)
        LOG('Tree', DEBUG, ' Returns ok=%s' % ok)
        return ok

    def _get_info(self, ob, plen):
        """Get info on one object."""
        info = None
        if self.info_method:
            method = getattr(ob, self.info_method, None)
            if method is not None:
                r = method()
                if isinstance(r, DictType):
                    info = self._new_tree(r)
                else:
                    LOG('TreeCache', ERROR, '_get_info returned non-dict %s'
                        % `r`)
        allowed_roles_and_users = _allowedRolesAndUsers(ob)
        local_roles = {}
        for k, v in ob.get_local_roles():
            local_roles['user:'+k] = v
        for k, v in ob.get_local_group_roles():
            local_roles['group:'+k] = v
        if info is None:
            # Empty info
            info = self._new_tree()
        ppath = ob.getPhysicalPath()
        info.update({'id': ob.getId(),
                     'url': ob.absolute_url(),
                     'path': '/'.join(ppath),
                     'rpath': '/'.join(ppath[plen:]),
                     'allowed_roles_and_users': allowed_roles_and_users,
                     'local_roles': local_roles,
                     })
        return info

    def _get_children(self, ob, depth, plen):
        children = PersistentList()
        for subob in ob.objectValues():
            if self._is_candidate(subob, plen):
                children.append(self._get_tree_r(subob, depth, plen))
        return children

    def _get_tree_r(self, ob, depth, plen):
        """Rebuild, starting at ob."""
        tree = self._get_info(ob, plen)
        children = self._get_children(ob, depth+1, plen)
        tree['depth'] = depth
        tree['children'] = children
        return tree

    def _get_tree(self, ob, depth):
        urltool = getToolByName(self, 'portal_url')
        portal = urltool.getPortalObject()
        plen = len(portal.getPhysicalPath())
        return self._get_tree_r(ob, depth, plen)

    def _finish_rebuild(self):
        pointers = PersistentList()
        flat = []
        self._flatten(self._tree, pointers, flat)
        self._pointers = pointers
        self._flat = flat

    def _flatten(self, tree, pointers, flat):
        """Flatten the informations."""
        d = tree.data.copy() # .data because tree is PersistentMapping
        pointers.append(tree)
        flat.append(d)
        has_children = d.has_key('children')
        d['nb_children'] = has_children and len(d['children']) or 0
        if has_children:
            del d['children']
            for subtree in tree['children']:
                self._flatten(subtree, pointers, flat)

    #
    # API
    #

    security.declareProtected(ViewManagementScreens, 'manage_rebuild')
    def manage_rebuild(self, REQUEST=None):
        """Rebuild all the tree."""
        self.rebuild()
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url()+'/manage_listTree')

    security.declarePublic('getRoot')
    def getRoot(self):
        """Get the root of this tree, as an rpath."""
        root = self.root
        if root.endswith('/'):
            root = root[:-1]
        if self.root and self.root.find('..') < 0 and self.root[:1] != '/':
            return root
        else:
            return ''

    def _copy_tree_from(self, tree, rpath=None):
        treerpath = tree['rpath']
        if rpath is not None and treerpath != rpath:
            # still searching
            for info in tree['children']:
                if rpath.startswith(info['rpath']):
                    return self._copy_tree_from(info, rpath)
            # not found in children
            return {}
        info = {}
        for k, v in tree.items():
            if k != 'children':
                info[k] = v
        children = []
        for child in tree['children']:
            children.append(self._copy_tree_from(child))
        info['children'] = children
        return info

    security.declareProtected(View, 'getTree')
    def getTree(self, path=None):
        """Return the cached tree, starting from path.

        Path may be None, a path or an rpath.
        """
        if path is None:
            rpath = self.getRoot()
        else:
            if not path.startswith('/'):
                rpath = path
            else:
                portal = getToolByName(self, 'portal_url').getPortalObject()
                portalpath = '/'.join(portal.getPhysicalPath())
                rpath = path[len(portalpath)+1:]
        return self._copy_tree_from(self._tree, rpath=rpath)

    security.declareProtected(View, 'getList')
    def getList(self, prefix=None, start_depth=0, stop_depth=999, filter=1):
        """Return the cached tree as a list.

        Only return the part between start_depth and stop_depth inclusive,
        that are under the prefix (an rpath).
        If filter=1, skip unviewable entries.

        Eeach node is a dictionnary containing the following information:
          id
          url (do not use)
          path
          rpath
          depth
          allowed_roles_and_users
          local_roles (local, no merging)
          children    (for the tree)
          nb_children (for the list)
          visible (0 or 1, when filter=0)
        """
        mtool = getToolByName(self, 'portal_membership')
        try:
            user = mtool.getAuthenticatedMember().getUser()
            allowed_roles_and_users = _getAllowedRolesAndUsers(user)
        except TypeError: 
            # XXX?? getUser() takes exactly 2 arguments (1 given)
            allowed_roles_and_users = ['Anonymous', 'group:role:Anonymous']
        res = []
        for info in self._flat:
            # check filter
            visible = 0
            for ur in info['allowed_roles_and_users']:
                if ur in allowed_roles_and_users:
                    visible = 1
                    break
            if filter and not visible:
                continue
            info['visible'] = visible
            # check prefix
            if prefix is not None:
                rpath = info['rpath']
                if rpath != prefix and not rpath.startswith(prefix+'/'):
                    continue
            # check depth
            depth = info['depth']
            if depth < start_depth or depth > stop_depth:
                continue
            res.append(info)
        return res

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
