# (C) Copyright 2003-2005 Nuxeo SARL <http://nuxeo.com>
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

import logging
from ZODB.loglevels import TRACE, BLATHER
from AccessControl import ClassSecurityInfo
from AccessControl import Unauthorized
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from AccessControl.User import UnrestrictedUser as BaseUnrestrictedUser
from Acquisition import aq_base, aq_inner
from BTrees.OOBTree import OOBTree
from Globals import InitializeClass, DTMLFile
from OFS.Folder import Folder

from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import View
from Products.CMFCore.permissions import ManagePortal
from Products.CMFCore.permissions import ViewManagementScreens

from Products.CPSUtil.text import truncateText
from Products.CPSCore.utils import getAllowedRolesAndUsersOfUser
from Products.CPSCore.utils import getAllowedRolesAndUsersOfObject
from Products.CPSCore.TreeCacheManager import get_treecache_manager

from Products.CPSCore.treemodification import ADD, REMOVE, MODIFY
from Products.CPSCore.treemodification import printable_op


from zope.app.event.interfaces import IObjectModifiedEvent
from zope.app.container.interfaces import IObjectMovedEvent
from zope.app.container.interfaces import IContainerModifiedEvent
from OFS.interfaces import IObjectWillBeMovedEvent
from interfaces import ICPSProxy

def intersects(a, b):
    for v in a:
        if v in b:
            return True
    return False

from zope.interface import implements
from Products.CPSCore.interfaces import ITreeTool
from Products.CPSCore.interfaces import ITreeCache


class UnrestrictedUser(BaseUnrestrictedUser):
    """Unrestricted user that still has an id."""
    def getId(self):
        """Return the ID of the user."""
        return self.getUserName()

logger = logging.getLogger('CPSCore.TreesTool')


class TreesTool(UniqueObject, Folder):
    """Trees Tool that caches information about the site's hierarchies.
    """

    implements(ITreeTool)

    id = 'portal_trees'
    meta_type = 'CPS Trees Tool'

    security = ClassSecurityInfo()

    manage_options = Folder.manage_options + (
    {'label': 'Export', 'action': 'manage_genericSetupExport.html'},
                    )

    _properties = Folder._properties + (
        {'id': 'ignore_events', 'type': 'boolean', 'mode': 'w',
         'label': "Ignore events"},
        )
    ignore_events = False

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, ob, infos=None):
        """Notification method called by the event service.

        Dispatches to the accurate caches notification methods.

        infos is ignored.
        """
        if self.ignore_events:
            return
        if event_type not in ('sys_add_cmf_object',
                              'sys_add_object',
                              'sys_del_object',
                              'sys_modify_object',
                              'sys_modify_security',
                              'sys_order_object',
                              'modify_object'):
            return

        path = ob.getPhysicalPath()
        logger.log(TRACE, "Got %s for %s", event_type, '/'.join(path))
        for cache in self.objectValues():
            if cache.isCandidate(ob):
                if event_type in ('sys_add_cmf_object', 'sys_add_object'):
                    op = ADD
                    info = None
                elif event_type == 'sys_del_object':
                    op = REMOVE
                    info = None
                elif event_type in ('sys_modify_object', 'modify_object'):
                    op = MODIFY
                    info = {'full': True}
                elif event_type == 'sys_modify_security':
                    op = MODIFY
                    info = {'security': True}
                elif event_type == 'sys_order_object':
                    op = MODIFY
                    info = {'order': True}
                else:
                    raise ValueError("Invalid event type %s" % event_type)
                get_treecache_manager().push(cache, op, path, info)

        """
        LOG('TreesTool', DEBUG, "Got %s for %s" %
            (event.__class__.__name__, '/'.join(path)))
        for cache in self.objectValues():
            if cache.isCandidate(ob):
                op = None
                info = None
                if IObjectWillBeMovedEvent.providedBy(event):
                    if event.oldParent is not None:
                        op = REMOVE
                elif IObjectMovedEvent.providedBy(event):
                    if event.newParent is not None:
                        op = ADD
                elif IContainerModifiedEvent.providedBy(event):
                    op = MODIFY
                    info = {'order': True}
                elif IObjectModifiedEvent.providedBy(event):
                    # XXX check descriptions for security here
                    # XXX also security is recursive!
                    op = MODIFY
                    info = {'full': True}
                if op is None:
                    continue
                get_treecache_manager().push(cache, op, path, info)
        """


    security.declarePrivate('flushEvents')
    def flushEvents(self):
        """Flush tree cache manager, which executes the modifications.
        """
        get_treecache_manager()()

    #
    # ZMI
    #

    def all_meta_types(self):
        return ({'name': 'CPS Tree Cache',
                 'action': 'manage_addCPSTreeCacheForm',
                 'permission': ManagePortal},)

    security.declareProtected(ViewManagementScreens,
                              'manage_addCPSTreeCacheForm')
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


class TreeCacheUpdater(object):
    """Get or update info about a cache.
    """
    def __init__(self, cache):
        self.cache = cache
        self.infos = getattr(cache, '_infos', None)
        self.portal = getToolByName(cache, 'portal_url').getPortalObject()
        self.plen = len(self.portal.getPhysicalPath())
        self.info_method = cache.info_method
        tmp_user = UnrestrictedUser('manager', '', ['Manager'], '')
        self.tmp_user = tmp_user.__of__(aq_inner(cache.acl_users))
        self.root = cache.getRoot()

    def getRpathFromPath(self, path):
        return '/'.join(path[self.plen:])

    def getRpath(self, ob):
        return self.getRpathFromPath(ob.getPhysicalPath())

    # Operations on objects

    def isCandidate(self, ob):
        """Return True if the object should be cached."""
        # Check under root
        if not self.root:
            return False
        rpath_slash = self.getRpath(ob)+'/'
        if not rpath_slash.startswith(self.root+'/'):
            return False
        # Check excluded rpaths
        for excluded_rpath in self.cache.excluded_rpaths:
            if rpath_slash.startswith(excluded_rpath+'/'):
                return False
        # Check portal types (meta_type already filtered)
        bob = aq_base(ob)
        type_names = self.cache.type_names or ()
        if getattr(bob, 'portal_type', None) not in type_names:
            return False

        return True

    def getNodeInfo(self, ob):
        """Compute info about one object.
        """
        info = {}
        if self.cache.info_method:
            method = getattr(ob, self.cache.info_method, None)
            if method is not None:
                doc = ob.getContent(lang='default')

                # Call the info method while being a temporary Manager
                # so that it can access protected methods.
                old_sm = getSecurityManager()
                try:
                    newSecurityManager(None, self.tmp_user)
                    info = method(doc=doc)
                finally:
                    setSecurityManager(old_sm)

                if not isinstance(info, dict):
                    logger.error("getNodeInfo returned non-dict %r", info)
                    info = {}
        info.update({
            'id': ob.getId(),
            'rpath': self.getRpath(ob),
            'portal_type': ob.portal_type,
            })
        if ICPSProxy.providedBy(ob):
            info['l10_titles'] = ob.getL10nTitles()
        info.update(self.getNodeSecurityInfo(ob))
        return info

    def getNodeSecurityInfo(self, ob):
        """Get the security info about one object.
        """
        allowed_roles_and_users = getAllowedRolesAndUsersOfObject(ob)
        local_roles = {}
        for k, v in ob.get_local_roles():
            local_roles['user:'+k] = v
        for k, v in ob.get_local_group_roles():
            local_roles['group:'+k] = v
        return {
            'allowed_roles_and_users': allowed_roles_and_users,
            'local_roles': local_roles,
            }

    def updateNode(self, ob):
        """Compute one node in the tree.

        Keeps children info from previous node if available.
        """
        rpath = self.getRpath(ob)
        old_info = self.infos.get(rpath)
        info = self.getNodeInfo(ob)
        if old_info is not None:
            info['depth'] = old_info['depth']
            info['children'] = old_info['children']
            info['nb_children'] = old_info['nb_children']
            self.infos[rpath] = info
        else:
            # Compute depth
            root = self.root
            depth = rpath.count('/') - root.count('/')
            info['depth'] = depth
            self.infos[rpath] = info
            self.updateChildrenInfo(ob)

    def updateChildrenInfo(self, ob):
        """Recompute the list of children a node has.
        """
        rpath = self.getRpath(ob)
        info = self.infos.get(rpath)
        if info is None:
            # Parent is outside of the tree
            return
        children = []
        ptype = getattr(aq_base(ob), 'portal_type', None)
        if ptype not in self.cache.terminal_nodes:
            for subob in ob.objectValues(self.cache.meta_types):
                if self.isCandidate(subob):
                    subrpath = self.getRpath(subob)
                    children.append(subrpath)
        info['children'] = children
        info['nb_children'] = len(children)
        self.infos[rpath] = info

    def makeTree(self, ob):
        """Recompute the tree starting from ob."""
        rpath = self.getRpath(ob)
        root = self.root
        depth = rpath.count('/') - root.count('/')
        self._makeTree(ob, depth)

    def _makeTree(self, ob, depth):
        """Recompute the tree starting from ob.

        Recursive method.
        """
        info = self.getNodeInfo(ob)
        subdepth = depth+1
        children = []
        ptype = getattr(aq_base(ob), 'portal_type', None)
        if ptype not in self.cache.terminal_nodes:
            for subob in ob.objectValues():
                if self.isCandidate(subob):
                    subrpath = self._makeTree(subob, subdepth)
                    children.append(subrpath)
        info['depth'] = depth
        info['children'] = children
        info['nb_children'] = len(children)
        rpath = info['rpath']
        self.infos[rpath] = info
        return rpath

    def updateSecurityUnder(self, ob):
        """Update security under an object.
        """
        rpath = self.getRpath(ob)
        info = self.infos.get(rpath)
        if info is not None:
            info.update(self.getNodeSecurityInfo(ob))
            self.infos[rpath] = info
        # Recurse
        for subob in ob.objectValues():
            if self.isCandidate(subob):
                self.updateSecurityUnder(subob)

    # Operations on physical paths

    def updateNodeAtPath(self, path):
        """Update a node.
        """
        ob = self.portal.unrestrictedTraverse(path)
        self.updateNode(ob)

    def updateChildrenInfoAtPath(self, path):
        """Update children info at a given physical path.
        """
        ob = self.portal.unrestrictedTraverse(path)
        self.updateChildrenInfo(ob)

    def addNodesUnderPath(self, path):
        """Add a node and all its subnodes.
        """
        ob = self.portal.unrestrictedTraverse(path)
        self.makeTree(ob)

    def deleteNodesUnderPath(self, path):
        """Delete all nodes at or under a given physical path.
        """
        rpath = self.getRpathFromPath(path)
        for key in list(self.infos.keys(rpath+'/', rpath+'/\xFF')):
            del self.infos[key]
        if rpath in self.infos:
            del self.infos[rpath]

    def fixParentOfPathAfterDelete(self, path):
        """Fix a parent's children info after a remove.
        """
        rpath = self.getRpathFromPath(path)
        prpath = self.getRpathFromPath(path[:-1])
        parent_info = self.infos.get(prpath)
        if parent_info is None:
            # Parent is outside of the tree
            return
        try:
            parent_info['children'].remove(rpath)
        except ValueError:
            pass
        else:
            parent_info['nb_children'] -= 1
            self.infos[prpath] = parent_info

    def updateSecurityUnderPath(self, path):
        """Update security info under a path.
        """
        ob = self.portal.unrestrictedTraverse(path)
        self.updateSecurityUnder(ob)

    # Operations on modificationt tree

    def updateTree(self, tree):
        """Replay modifications to a ModificationTree.

        Here events have been compressed, and we have to recurse for ADD
        and REMOVE.
        """
        for op, path, info in tree.get():
            logger.log(TRACE, "  replaying %s %s %s",
                       printable_op(op), '/'.join(path), info)
            if op == ADD:
                # First, delete old info about it
                self.deleteNodesUnderPath(path)
                # Then add new info
                self.addNodesUnderPath(path)
                # Fixup the parent because order is now unknown.
                self.updateChildrenInfoAtPath(path[:-1])
            elif op == REMOVE:
                self.deleteNodesUnderPath(path)
                # Fixup the parent
                self.fixParentOfPathAfterDelete(path)
            else: # op == MODIFY
                if 'full' in info:
                    self.updateNodeAtPath(path)
                else:
                    if 'security' in info:
                        self.updateSecurityUnderPath(path)
                    if 'order' in info:
                        self.updateChildrenInfoAtPath(path)


class TreeCache(SimpleItemWithProperties):
    """Tree cache object, caches information about one hierarchy.
    """

    implements(ITreeCache)

    meta_type = 'CPS Tree Cache'

    security = ClassSecurityInfo()
    security.declareObjectProtected(View)

    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w',
         'label': 'Title'},
        {'id': 'root', 'type': 'string', 'mode': 'w',
         'label': 'Root'},
        {'id': 'type_names', 'type': 'lines', 'mode': 'w',
         'label': 'Portal Types'},
        {'id': 'meta_types', 'type': 'lines', 'mode': 'w',
         'label': 'Meta Types'},
        {'id': 'excluded_rpaths', 'type': 'lines', 'mode': 'w',
         'label': 'Excluded rpaths'},
        {'id': 'info_method', 'type': 'string', 'mode': 'w',
         'label': 'Info Method'},
        {'id': 'terminal_nodes', 'type': 'lines', 'mode': 'w',
         'label': "Portal types of terminal nodes (children won't be cached)"},
        )

    title = ''
    root = ''
    type_names = ()
    meta_types = ()
    excluded_rpaths = ()
    info_method = ''
    terminal_nodes = ()

    def __init__(self, id, **kw):
        self._setId(id)
        self._clear()

    def _clear(self):
        self._infos = OOBTree() # rpath -> info dict

    def _maybeUpgrade(self):
        """Upgrade from the old format if needed."""
        if self.__dict__.has_key('_tree'):
            self._upgrade()

    def _upgrade(self):
        """Upgrade from the old format."""
        logger.info("Upgrading tree %s", self.getId())
        delattr(self, '_tree')
        delattr(self, '_pointers')
        delattr(self, '_flat')
        self._clear()
        self.rebuild()

    security.declareProtected(ViewManagementScreens, 'all_type_names')
    def all_type_names(self):
        """Return the allowed type names."""
        res = []
        ttool = getToolByName(self, 'portal_types')
        for ti in ttool.listTypeInfo():
            id = ti.getId()
            if id.startswith('CPS Proxy'):
                continue
            res.append(id)
        res.sort()
        return res

    security.declareProtected(View, 'isCandidate')
    def isCandidate(self, ob):
        """Return True if the object should be cached."""
        return TreeCacheUpdater(self).isCandidate(ob)

    security.declarePrivate('rebuild')
    def rebuild(self):
        """Rebuild all the tree."""
        self._clear()
        portal = getToolByName(self, 'portal_url').getPortalObject()
        root = self.getRoot()
        if not root:
            return
        root_ob = portal.unrestrictedTraverse(root, None)
        if root_ob is None:
            # Root not present, actually legal (and common during installation)
            logger.log(BLATHER, "Root %r not present when rebuilding %s",
                       root, self.getId())
            return
        TreeCacheUpdater(self).makeTree(root_ob)

    # Called by the TreeCacheManager

    security.declarePrivate('updateTree')
    def updateTree(self, tree):
        """Replay modifications to a ModificationTree.
        """
        self._maybeUpgrade()
        TreeCacheUpdater(self).updateTree(tree)

    def _getModificationTree(self):
        """Debugging: get the current modification tree.
        """
        return get_treecache_manager()._getModificationTree(self)

    def _localize(self, info, locale_keys, locale):
        """Localize info attributes specified in locale_keys into the locale
        language.

        Available keys are:
        - title
          - title_or_id
          - short_title
        - description
        Other keys are ignored
        """
        if ('title' in locale_keys
            and info.has_key('l10n_titles')
            and info['l10n_titles'].has_key(locale)):
            info['title'] = info['l10n_titles'][locale]
            if info['title']:
                title_or_id = info['title']
            else:
                title_or_id = info['id']
            if 'title_or_id' in locale_keys:
                info['title_or_id'] = title_or_id
            if 'short_title' in locale_keys:
                info['short_title'] = truncateText(title_or_id)

        # XXX: make this part generic (any key instead of description)
        if ('description' in locale_keys
            and info.has_key('l10n_descriptions')
            and info['l10n_descriptions'].has_key(locale)):
            info['description'] = info['l10n_descriptions'][locale]

        return info

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
        # XXX the checks should be done at changeProperties time.
        root = self.root
        if root.endswith('/'):
            root = root[:-1]
        if root and root.find('..') < 0 and root[0] != '/':
            return root
        else:
            return ''

    security.declareProtected(View, 'getList')
    def getList(self, prefix=None, start_depth=0, stop_depth=999,
                filter=True, order=True, count_children=False,
                locale_keys=None, locale_lang=None, REQUEST=None):
        """Return a subportion of the tree, flattened into a list.

        Only returns the part between start_depth and stop_depth inclusive,
        that are under the prefix (an rpath).

        If filter is true, skips unviewable entries (slower).

        If order is true, keeps original zodb order (slower).

        If count_children is true, get info about nb_children (slower).

        If locale_keys is not None, info keys are translated into locale_lang
        (slower).

        Each list element is a mapping containing the following keys:
          id
          rpath
          portal_type
          depth       (depth starting from the cache root)
          nb_children
          allowed_roles_and_users
          local_roles (local roles without merging)
          visible     (boolean)
        """
        if REQUEST is not None:
            raise Unauthorized

        self._maybeUpgrade()

        user = getSecurityManager().getUser()
        whoami = getAllowedRolesAndUsersOfUser(user)

        infos = self._infos
        if prefix is None:
            rpaths = infos.keys()
        else:
            rpaths = infos.keys(prefix+'/', prefix+'/\xFF')
            if infos.has_key(prefix):
                rpaths = list(rpaths)
                rpaths.insert(0, prefix)

        res = []

        if not order:
            for rpath in rpaths:
                info = infos[rpath]

                # Check depth
                depth = info['depth']
                if depth < start_depth or depth > stop_depth:
                    continue

                # Check filter
                visible = intersects(info['allowed_roles_and_users'], whoami)
                if filter and not visible:
                    continue
                info = info.copy()
                info['visible'] = visible
                del info['children']

                res.append(info)

        else: # order
            done = {}
            rest = list(rpaths)
            while rest:
                rpath = rest.pop(0)
                if done.has_key(rpath):
                    continue

                # The todo list is a list of paths to process in order,
                # with their children.
                todo = [rpath]
                while todo:
                    rpath = todo.pop(0)
                    if done.has_key(rpath):
                        continue
                    done[rpath] = None
                    info = infos.get(rpath)
                    if info is None:
                        # Inconsistent tree, don't break completely
                        continue

                    # update todo list if appropriate before any filering
                    # so that discarding doesn't break order
                    # Process children in order (depth first)
                    depth = info['depth']
                    children = info['children']
                    if depth < stop_depth:
                        todo = children + todo

                    # Check depth (second statement there for safety)
                    if depth < start_depth or depth > stop_depth:
                        continue

                    # Check visibility filter
                    visible = intersects(info['allowed_roles_and_users'],
                                         whoami)
                    if filter and not visible:
                        continue

                    # Keep it
                    info = info.copy()
                    info['visible'] = visible
                    del info['children']

                    res.append(info)



        if count_children and (filter or stop_depth != 999):
            # Compute nb_children for each level
            counters = {}
            for info in res:
                rpath = info['rpath']
                if '/' not in rpath:
                    continue
                parent = rpath[:rpath.rfind('/')]
                counters[parent] = counters.setdefault(parent, 0) + 1
            for info in res:
                info['nb_children'] = counters.get(info['rpath'], 0)


        # Check locale
        if locale_keys is not None:
            res = [self._localize(info, locale_keys, locale_lang)
                    for info in res]
        return res

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Tree',
         'action': 'manage_listTree',
         },
        ) + SimpleItemWithProperties.manage_options + (
        {'label': 'Export', 'action': 'manage_genericSetupExport.html'},
                )

    security.declareProtected(ViewManagementScreens, 'manage_listTree')
    manage_listTree = DTMLFile('zmi/tree_content', globals())
