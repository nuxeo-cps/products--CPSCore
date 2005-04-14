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

from zLOG import LOG, DEBUG, ERROR
from Globals import InitializeClass, DTMLFile
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from AccessControl import Unauthorized
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from AccessControl.User import UnrestrictedUser as BaseUnrestrictedUser

from BTrees.OOBTree import OOBTree
from OFS.Folder import Folder

from Products.CMFCore.permissions \
    import View, ManagePortal, ViewManagementScreens
from Products.CMFCore.utils \
    import SimpleItemWithProperties, UniqueObject, getToolByName

from Products.CPSCore.utils import getAllowedRolesAndUsersOfUser
from Products.CPSCore.utils import getAllowedRolesAndUsersOfObject
from Products.CPSUtil.text import truncateText


def intersects(a, b):
    for v in a:
        if v in b:
            return True
    return False


class UnrestrictedUser(BaseUnrestrictedUser):
    """Unrestricted user that still has an id."""
    def getId(self):
        """Return the ID of the user."""
        return self.getUserName()


class TreesTool(UniqueObject, Folder):
    """Trees Tool that caches information about the site's hierarchies.
    """

    id = 'portal_trees'
    meta_type = 'CPS Trees Tool'

    security = ClassSecurityInfo()

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, ob, infos):
        """Notification method called by the event service.

        Dispatches to the caches notification methods.
        """

        if event_type not in ('sys_add_cmf_object', # XXX ugh clean this up
                              'sys_del_object',
                              'sys_modify_object',
                              'sys_modify_security',
                              'sys_order_object',
                              'modify_object'):
            return
        LOG('TreesTool', DEBUG, 'Got %s for %s'
            % (event_type, '/'.join(ob.getPhysicalPath())))
        for tree in self.objectValues():
            tree.notify_tree(event_type, ob, infos)

    #
    # ZMI
    #

    def all_meta_types(self):
        return ({'name': 'CPS Tree Cache',
                 'action': 'manage_addCPSTreeCacheForm',
                 'permission': ManagePortal},)

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
    type_names = ()
    meta_types = ()
    info_method = ''

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
        LOG('TreeCache._upgrade', DEBUG, 'Upgrading tree %s' % self.getId())

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

    security.declarePrivate('notify_tree')
    def notify_tree(self, event_type, ob, infos):
        """Notification method called when an event is received.

        Called by the the trees tool's notify method.
        """
        self._maybeUpgrade()

        urltool = getToolByName(self, 'portal_url')
        plen = len(urltool.getPortalObject().getPhysicalPath())
        rpath = '/'.join(ob.getPhysicalPath()[plen:])
        if not self._isCandidate(ob, plen):
            return
        LOG('TreeCache.notify_tree', DEBUG, "%s: %s for %s"
            % (self.getId(), event_type, rpath))

        if event_type == 'sys_add_cmf_object':
            self.updateNode(ob)
            parent = aq_parent(aq_inner(ob))
            self.updateChildrenInfo(parent)
        elif event_type == 'sys_del_object':
            self.deleteNode(ob)
        elif event_type == 'sys_order_object':
            self.updateChildrenInfo(ob)
        elif event_type == 'sys_modify_security':
            # This event has to do recursion by itself
            self.makeTree(ob)
        else: # event_type == 'modify_object' / 'sys_modify_object'
            self.updateNode(ob)

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
            LOG('TreeCache.rebuild', ERROR,
                "%s: bad root '%s'" % (self.getId(), root))
            return
        self.makeTree(root_ob)

    def _isCandidate(self, ob, plen):
        """Return True if the object should be cached."""
        #LOG('Tree', DEBUG, 'Is %s candidate?' % ob.getId())
        bob = aq_base(ob)
        if self.meta_types and getattr(bob, 'meta_type', None) not in self.meta_types:
            #LOG('Tree', DEBUG, ' No, mt=%s' % getattr(bob, 'meta_type', None))
            return False
        type_names = self.type_names or [] # Stupid, may be ''.
        if getattr(bob, 'portal_type', None) not in type_names:
            #LOG('Tree', DEBUG,
            #    ' No, pt=%s' % getattr(bob, 'portal_type', None))
            return False
        root = self.getRoot()
        if not root:
            return True
        rpath = '/'.join(ob.getPhysicalPath()[plen:])
        ok = (rpath+'/').startswith(root+'/')
        #LOG('Tree', DEBUG, ' Returns ok=%s' % ok)
        return ok

    security.declarePrivate('getNodeInfo')
    def getNodeInfo(self, ob, plen):
        """Compute info about one object."""
        info = {}
        if self.info_method:
            method = getattr(ob, self.info_method, None)
            if method is not None:
                doc = ob.getContent(lang='default')

                # Call the info method while being a temporary Manager
                # so that it can access protected methods.
                old_sm = getSecurityManager()
                tmp_user = UnrestrictedUser('manager', '', ['Manager'], '')
                tmp_user = tmp_user.__of__(self.acl_users)
                try:
                    newSecurityManager(None, tmp_user)
                    info = method(doc=doc)
                finally:
                    setSecurityManager(old_sm)

                if not isinstance(info, dict):
                    LOG('TreeCache', ERROR,
                        "getNodeInfo returned non-dict %s" % `info`)
                    info = {}
        allowed_roles_and_users = getAllowedRolesAndUsersOfObject(ob)
        local_roles = {}
        for k, v in ob.get_local_roles():
            local_roles['user:'+k] = v
        for k, v in ob.get_local_group_roles():
            local_roles['group:'+k] = v
        ppath = ob.getPhysicalPath()
        info.update({'id': ob.getId(),
                     'rpath': '/'.join(ppath[plen:]),
                     'portal_type': ob.portal_type,
                     'allowed_roles_and_users': allowed_roles_and_users,
                     'local_roles': local_roles,
                     })
        return info

    security.declarePrivate('makeTree')
    def makeTree(self, ob):
        """Recompute the tree starting from ob."""
        urltool = getToolByName(self, 'portal_url')
        plen = len(urltool.getPortalObject().getPhysicalPath())
        rpath = urltool.getRelativeUrl(ob)
        root = self.getRoot()
        depth = rpath.count('/') - root.count('/')
        self._makeTree(ob, depth, plen)

    security.declarePrivate('_makeTree')
    def _makeTree(self, ob, depth, plen):
        """Recompute the tree starting from ob.

        Recursive method.
        """
        info = self.getNodeInfo(ob, plen)
        subdepth = depth+1
        children = []
        for subob in ob.objectValues():
            if self._isCandidate(subob, plen):
                subrpath = self._makeTree(subob, subdepth, plen)
                children.append(subrpath)
        info['depth'] = depth
        info['children'] = children
        info['nb_children'] = len(children)
        rpath = info['rpath']
        self._infos[rpath] = info
        return rpath

    def updateNode(self, ob):
        """Compute one node in the tree.

        Keeps children info from previous node if available.
        """
        urltool = getToolByName(self, 'portal_url')
        plen = len(urltool.getPortalObject().getPhysicalPath())
        rpath = urltool.getRelativeUrl(ob)
        old_info = self._infos.get(rpath)
        info = self.getNodeInfo(ob, plen)
        if old_info is not None:
            info['depth'] = old_info['depth']
            children = old_info['children']
            info['children'] = children
            info['nb_children'] = len(children)
            self._infos[rpath] = info
        else:
            # Compute depth
            root = self.getRoot()
            depth = rpath.count('/') - root.count('/')
            info['depth'] = depth
            self._infos[rpath] = info
            self.updateChildrenInfo(ob)

    def updateChildrenInfo(self, ob):
        """Recompute info about children of a node."""
        urltool = getToolByName(self, 'portal_url')
        plen = len(urltool.getPortalObject().getPhysicalPath())
        rpath = urltool.getRelativeUrl(ob)
        info = self._infos.get(rpath)
        if info is None:
            # Parent is outside of the tree
            return
        children = []
        for subob in ob.objectValues():
            if self._isCandidate(subob, plen):
                subrpath = urltool.getRelativeUrl(subob)
                children.append(subrpath)
        info['children'] = children
        info['nb_children'] = len(children)
        self._infos[rpath] = info

    def deleteNode(self, ob):
        """Delete a node from the tree."""
        urltool = getToolByName(self, 'portal_url')
        rpath = urltool.getRelativeUrl(ob)

        # Update parent's children list
        parent = aq_parent(aq_inner(ob))
        prpath = urltool.getRelativeUrl(parent)
        parent_info = self._infos.get(prpath)
        if parent_info is not None:
            try:
                parent_info['children'].remove(rpath)
            except ValueError:
                pass
            else:
                parent_info['nb_children'] -= 1
                self._infos[prpath] = parent_info

        # Remove object info
        try:
            del self._infos[rpath]
        except KeyError:
            pass

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
                    info = infos[rpath]

                    # Check depth
                    depth = info['depth']
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
                    children = info['children']
                    del info['children']

                    res.append(info)

                    # Next, process children in order (depth first)
                    todo = children + todo

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
        ) + SimpleItemWithProperties.manage_options

    security.declareProtected(ViewManagementScreens, 'manage_listTree')
    manage_listTree = DTMLFile('zmi/tree_content', globals())
