# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Object Repository Tool.

The object repository tool stores versions of documents.
It also stores workflow-related information for those documents.
"""

from zLOG import LOG, ERROR, DEBUG, TRACE
import random
from Globals import InitializeClass, DTMLFile
from cStringIO import StringIO
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import ClassSecurityInfo
from AccessControl.Permission import Permission, name_trans

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.CMFCorePermissions import ManagePortal
from Products.CMFCore.PortalFolder import PortalFolder
from Products.DCWorkflow.utils import modifyRolesForPermission
from Products.BTreeFolder2.BTreeFolder2 import BTreeFolder2
from BTrees.OOBTree import OOBTree

from Products.CPSWorkflow.workflowtool import Config_id
from Products.CPSCore.CPSTypes import TypeConstructor, TypeContainer
from Products.CPSCore.EventServiceTool import getEventService


class NoWorkflowConfiguration:
    """Class for a workflow configuration object that denies
    all workflows."""

    security = ClassSecurityInfo()

    security.declarePrivate('getPlacefulChainFor')
    def getPlacefulChainFor(self, portal_type, start_here=None):
        """No workflow chain is allowed."""
        return ()

InitializeClass(NoWorkflowConfiguration)


def setLocalRolesWithGroups(ob, lroles):
    """Set all the local roles and group local roles.

    Returns True if something was changed.
    """
    # XXX move this to NuxUserGroups
    #LOG('obrep', DEBUG, 'setlocal: ob=%s lroles=%s'
    #    % ('/'.join(ob.getPhysicalPath()), lroles,))
    udict = {}
    gdict = {}
    for k, roles in lroles.items():
        if k.startswith('user:'):
            uid = k[5:]
            udict[uid] = list(roles)
        elif k.startswith('group:'):
            gid = k[6:]
            gdict[gid] = list(roles)
    changed = 0
    uroles = getattr(ob, '__ac_local_roles__', None) or {}
    groles = getattr(ob, '__ac_local_group_roles__', None) or {}
    if uroles != udict:
        #LOG('obrep', DEBUG, ' set udict=%s' % (udict,))
        ob.__ac_local_roles__ = udict
        changed = 1
    if groles != gdict:
        #LOG('obrep', DEBUG, ' set gdict=%s' % (gdict,))
        ob.__ac_local_group_roles__ = gdict
        changed = 1
    #LOG('obrep', DEBUG, ' changed=%s' % changed)
    return changed


class ObjectRepositoryTool(UniqueObject,
                           BTreeFolder2, PortalFolder,
                           TypeConstructor, TypeContainer):
    """An object repository stores objects that can be
    available in several versions.

    It also stores centrally the workflow history for all the versions
    of an object.

    It can be queried for the best version of a given object matching
    a set of constraints, for instance on language.

    docid is an identifier unique to the repository that describes a set
    of revisions of one object.

    rev is a revision of one object.
    """

    id = 'portal_repository'
    meta_type = 'CPS Repository Tool'
    portal_type = meta_type

    security = ClassSecurityInfo()

    def __init__(self):
        BTreeFolder2.__init__(self, self.id)
        self._histories = OOBTree()

    security.declarePrivate('keyRange')
    def keyRange(self, k1, k2):
        return self._tree.keys(k1, k2)

    #
    # API
    #

    security.declarePrivate('getFreeDocid')
    def getFreeDocid(self):
        """Get a free docid."""

        while 1:
            docid = str(random.randrange(1, 2147483600))
            if not self.keyRange(docid+'__0001', docid+'__9999'):
                return docid

    security.declarePrivate('getFreeRevision')
    def getFreeRevision(self, docid):
        """Get a free revision for a docid.

        Returns a revision one more than the last used.
        """
        existingRevs = self.keyRange(docid+'__0001', docid+'__9999')
        if len(existingRevs):
            # this new way of getting the highest revision
            # relies on the fact that keyRange returns a
            # lexicographically sorted sequence of ids
            did, rev = self._splitId(existingRevs[-1])
            return rev + 1
        else:
            return 1

    security.declarePrivate('createRevision')
    def createRevision(self, docid_, type_name_, *args, **kw):
        """Create an object with docid and a new revision in the repository.

        Returns the newly created object and its revision.

        (Called by ProxyTool.)
        """
        rev = self.getFreeRevision(docid_)
        id = self._getId(docid_, rev)
        ob = self.constructContent(type_name_, id, *args, **kw)
        evtool = getEventService(self)
        evtool.notify('sys_add_cmf_object', ob, {})
        # XXX or call ob.manage_afterCMFAdd(ob, self) ? recurse ?
        return ob, rev

    security.declarePrivate('delObjectRevision')
    def delObjectRevision(self, docid, rev):
        """Delete a revision of an object."""
        id = self._getId(docid, rev)
        self._delObject(id)

    security.declarePrivate('hasObjectRevision')
    def hasObjectRevision(self, docid, rev):
        """Test whether the repository has a given revision of an object."""
        id = self._getId(docid, rev)
        return self.hasObject(id)

    security.declarePrivate('getObjectRevision')
    def getObjectRevision(self, docid, rev):
        """Get a revision of an object.

        (Called by ProxyTool.)
        """
        id = self._getId(docid, rev)
        try:
            return self._getOb(id)
        except KeyError:
            LOG('ObjectRepositoryTool', ERROR,
                'Did not find expected document %s' % id)
            raise

    # XXX unused except by unit tests
    security.declarePrivate('delObjectRevisions')
    def delObjectRevisions(self, docid):
        """Delete all the revisions of an object."""
        prefix = self._getIdPrefix(docid)
        # XXX costly
        ids_to_delete = [id for id in self.objectIds()
                         if id.startswith(prefix)]
        for id in ids_to_delete:
            self._delObject(id)

        # Warning: don't do:
        # for id in self.objectIds():
        #     if ...: self._delObject(id)
        # because self.objectIds() is a live object (<OOBTreeItems>).

    security.declarePrivate('listAll')
    def listAll(self):
        """List all (docid, rev) in the repository."""
        items = []
        for id in self.objectIds():
            docid, rev = self._splitId(id)
            if docid is None:
                continue
            items.append((docid, rev))
        return items

    security.declarePrivate('listDocids')
    def listDocids(self):
        """List all the docids in the repository."""
        idd = {}
        has = idd.has_key
        for id in self.objectIds():
            docid, rev = self._splitId(id)
            if docid is None:
                continue
            if has(docid):
                continue
            idd[docid] = None
        return idd.keys()

    security.declarePrivate('listRevisions')
    def listRevisions(self, docid):
        """List all the revisions available for a given docid."""
        revs = []
        for id in self.keyRange(docid+'__0001', docid+'__9999'):
            did, rev = self._splitId(id)
            revs.append(rev)
        return revs

    security.declarePublic('getDocidAndRevisionFromObjectId')
    def getDocidAndRevisionFromObjectId(self, id):
        """Get docid and rev from an object id (gotten from catalog).

        (Called by ProxyTool.)
        """
        if self.hasObject(id):
            return self._splitId(id)
        else:
            return (None, None)

    security.declarePublic('isObjectInRepository')
    def isObjectInRepository(self, ob):
        """Test if an object is in the repository."""
        return ob.getPhysicalPath()[:-1] == self.getPhysicalPath()

    security.declarePrivate('freezeRevision')
    def freezeRevision(self, docid, rev):
        """Freeze a version of a document.

        Any modification to a frozen version should be forbidden by the
        rest of the system.

        There's no way to unfreeze a version without cloning it.

        (Called by ProxyTool.)
        """
        ob = self.getObjectRevision(docid, rev)
        # Don't write to ZODB if already frozen.
        if not getattr(aq_base(ob), '_cps_frozen', 0):
            ob._cps_frozen = 1
            # Unacquire modification permission.
            modifyRolesForPermission(ob, ModifyPortalContent, ('Manager',))

    security.declarePrivate('isRevisionFrozen')
    def isRevisionFrozen(self, docid, rev): # XXX unused?
        """Is a version frozen?"""
        ob = self.getObjectRevision(docid, rev)
        return getattr(ob, '_cps_frozen', 0)

    security.declarePrivate('copyRevision')
    def copyRevision(self, docid, rev, new_docid=None):
        """Copy a revision of an object into a new revision.

        If a new_docid is specified, create the new revision in that
        one.

        Returns the newly created (unfrozen) object and its revision.

        May be called by ProxyTool.
        """
        if new_docid is None:
            new_docid = docid
        ob = self.getObjectRevision(docid, rev)
        newrev = self.getFreeRevision(new_docid)
        newid = self._getId(new_docid, newrev)
        newob = self.copyContent(ob, newid)
        if hasattr(newob, '_cps_frozen'):
            delattr(newob, '_cps_frozen')
        # Reset permission to acquiring, so that when the security is reset
        # by the caller, everything works.
        modifyRolesForPermission(newob, ModifyPortalContent, [])
        # XXX add some info to the history
        return newob, newrev

    security.declarePrivate('getUnfrozenRevision')
    def getUnfrozenRevision(self, docid, rev):
        """Get an unfrozen version of an object.

        Returns the unfrozen object and its revision.

        (Called by ProxyTool.)
        """
        ob = self.getObjectRevision(docid, rev)
        if not getattr(aq_base(ob), '_cps_frozen', 0):
            return ob, rev
        return self.copyRevision(docid, rev)

    security.declarePrivate('getPermissionRole')
    def getPermissionRole(self, perm):
        """Get a special role mapping only to a permission.

        Register it if it doesn't exist yet.
        """
        role = 'permission:' + perm.translate(name_trans)
        if role not in self.__ac_roles__:
            # Register the role and add its permission.
            self._addRole(role)
            for inhp in self.ac_inherited_permissions(1):
                name, data = inhp[:2]
                if name == perm:
                    p = Permission(name, data, self)
                    # Set permission to unacquire, and to Manager.
                    p.setRoles(('Manager', role))
                    break
        return role

    security.declarePrivate('_registerPermissionRolesFor')
    def _registerPermissionRolesFor(self, ob):
        """Register all special permission roles mentionned in ob."""
        done = {}
        lroles = getattr(ob, '__ac_local_roles__', None) or {}
        lroles.update(getattr(ob, '__ac_local_group_roles__', None) or {})
        for k, roles in lroles.items():
            for role in roles:
                if done.has_key(role):
                    continue
                done[role] = None
                if role.startswith('permission:'):
                    tperm = role[len('permission:'):]
                    # Find corresponding untranslated permission name.
                    perm = None
                    for inhp in self.ac_inherited_permissions(1):
                        name = inhp[0]
                        if name.translate(name_trans) == tperm:
                            perm = name
                            break
                    if perm is None:
                        LOG('ObjectRepositoryTool', ERROR,
                            '_registerPermissionRolesFor perm %s' % tperm)
                        continue
                    # Register if needed.
                    self.getPermissionRole(perm)

    security.declarePrivate('setRevisionSecurity')
    def setRevisionSecurity(self, docid, rev, userperms):
        """Set the security on an object.

        userperms is a dict of {user: [sequence of permissions]}
        user is user:uid or group:gid

        Returns True if security was changed.

        (Called by ProxyTool.)
        """
        LOG('ObjectRepositoryTool', TRACE,
            'setRevisionSecurity docid=%s rev=%s perms=%s' %
            (docid, rev, userperms))
        ob = self.getObjectRevision(docid, rev)
        lroles = {}
        for user, perms in userperms.items():
            roles = [self.getPermissionRole(perm) for perm in perms]
            lroles[user] = roles
        changed = setLocalRolesWithGroups(ob, lroles)
        if changed:
            ob.reindexObjectSecurity()
        return changed

    #
    # Staging
    #

    security.declarePrivate('exportObjectRevision')
    def exportObjectRevision(self, docid, rev):
        """Export a given revision of an object into a string."""
        ob = self.getObjectRevision(docid, rev)
        f = StringIO()
        ob._p_jar.exportFile(ob._p_oid, f)
        return f.getvalue()

    security.declarePrivate('importObject')
    def importObject(self, s):
        """Import an object from a string."""
        # Import object.
        f = StringIO(s)
        where = self
        connection = where._p_jar
        while connection is None:
            where = aq_parent(aq_inner(where))
            connection = where._p_jar
        ob = connection.importFile(f)
        # Register special permissions roles.
        self._registerPermissionRolesFor(ob)
        # Set the object (this will recatalog).
        id = ob.getId()
        if self.hasObject(id):
            self._delObject(id)
        self._setObject(id, ob)
        LOG('ObjectRepositoryTool', DEBUG, 'importObject id=%s' % id)

    #
    # Management
    #

    # Protect tool's default view against unauthorized accesses
    security.declareProtected(ManagePortal, 'manage_main')

    security.declareProtected(ManagePortal, 'getManagementInformation')
    def getManagementInformation(self):
        """Return management info.

        Return a list of ids used, and of those that are used by no proxy.

        Return a dictionnary with information:
          nb_revs: total number of revisions
          nb_docids: total number of docids
          nb_unused_docids: number of unused docids
          nb_unused_revs: total number of unused revision
          nb_unused_revs_docids: number of revisions corresponding to
                                 unused docids
          nb_live_revs: number of used revisions
          nb_archived_revs: number of unused revisions corresponding to
                            used docids
          ids_unused_revs_docids: ids for revision of unused docids
        """
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool_infos = pxtool.getRevisionsUsed()


        nb_revs = 0
        docids_d = {} # all docids
        unused_docids_d = {} # all docids that are unused
        ids_unused_revs_docids = [] # ids for revs of unused docids
        ids_unused_revs = [] # ids for unused revs
        for id in self.objectIds():
            docid, rev = self._splitId(id)
            if docid is None:
                LOG('ObjectRepositoryTool', DEBUG,
                    "Bad id in repository: '%s'" % id)
                continue
            nb_revs += 1
            docids_d[docid] = None
            if not pxtool_infos.has_key(docid):
                unused_docids_d[docid] = None
                ids_unused_revs_docids.append(id)
                ids_unused_revs.append(id)
            elif not pxtool_infos[docid].has_key(rev):
                ids_unused_revs.append(id)
        nb_docids = len(docids_d)
        nb_unused_docids = len(unused_docids_d)
        nb_unused_revs = len(ids_unused_revs)
        nb_unused_revs_docids = len(ids_unused_revs_docids)
        nb_live_docids = nb_docids - nb_unused_docids
        nb_live_revs = nb_revs - nb_unused_revs
        nb_archived_revs = nb_unused_revs - nb_unused_revs_docids

        return {
            'nb_revs': nb_revs,
            'nb_docids': nb_docids,
            'nb_unused_docids': nb_unused_docids,
            'nb_unused_revs': nb_unused_revs,
            'nb_live_docids': nb_live_docids,
            'nb_live_revs': nb_live_revs,
            'nb_unused_revs_docids': nb_unused_revs_docids,
            'nb_archived_revs': nb_archived_revs,
            'ids_unused_revs_docids': ids_unused_revs_docids,
            }

    security.declareProtected(ManagePortal, 'purgeDeletedRevisions')
    def purgeDeletedRevisions(self):
        infos = self.getManagementInformation()
        ids_to_del = infos['ids_unused_revs_docids']
        LOG('purgeDeletedRevisions', DEBUG, 'deleting %s' % ids_to_del)
        self.manage_delObjects(ids_to_del)

    security.declareProtected(ManagePortal, 'purgeArchivedRevisions')
    def purgeArchivedRevisions(self, keep_max):
        """Purge archived revisions.

        Keeps no more than keep_max archives per docid.
        """
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool_infos = pxtool.getRevisionsUsed()

        docids_archives = {}

        for id in self.objectIds():
            docid, rev = self._splitId(id)
            if docid is None:
                continue
            if not pxtool_infos.has_key(docid):
                # deleted
                continue
            if pxtool_infos[docid].has_key(rev):
                # live
                continue
            docids_archives.setdefault(docid, []).append((rev, id))
        ids_to_del = []
        for docid, revids in docids_archives.items():
            if keep_max > 0:
                revids.sort()
                revids = revids[:-keep_max]
            for rev, id in revids:
                ids_to_del.append(id)
        LOG('purgeArchivedRevisions', DEBUG, 'keep_max=%s, deleting %s'
            % (keep_max, ids_to_del))
        self.manage_delObjects(ids_to_del)

    #
    # Id generation
    #

    def _getIdPrefix(self, docid):
        return '%s__' % docid

    # XXX: maybe rename this to _makeId since there is a possible confusion
    # with standard method getId().
    def _getId(self, docid, rev):
        return '%s__%04d' % (docid, rev)

    def _splitId(self, id):
        try:
            docid, rev = id.split('__')
            rev = int(rev)
        except ValueError:
            LOG('ObjectRepositoryTool', ERROR, 'Cannot split id %s' % id)
            return (None, None)
        else:
            return (docid, rev)

    #
    # Workflow history management
    #

    #def _checkHistoryPresent(self):
    #    """Upgrades: check that _histories is present."""
    #    if not hasattr(aq_base(self), '_histories'):
    #        self._histories = OOBTree()

    security.declarePrivate('getHistory')
    def getHistory(self, docid):
        """Get the workflow history for a docid, or None."""
        #self._checkHistoryPresent()
        return self._histories.get(docid)

    security.declarePrivate('setHistory')
    def setHistory(self, docid, history):
        """Set the workflow history for a docid."""
        #self._checkHistoryPresent()
        self._histories[docid] = history

    #
    # Forbid any workflow
    #

    # This done later by using setattr because the id is variable.
    #.cps_workflow_configuration = NoWorkflowConfiguration()

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Management',
         'action': 'manage_repoInfo',
        },
        ) + BTreeFolder2.manage_options

    security.declareProtected(ManagePortal, 'manage_repoInfo')
    manage_repoInfo = DTMLFile('zmi/repo_repoInfo', globals())

    security.declareProtected(ManagePortal, 'manage_purgeArchivedRevisions')
    def manage_purgeArchivedRevisions(self, keep_max, REQUEST=None):
        """Purge archived revisions.

        Keeps no more than keep_max archives per docid.
        """
        keep_max = int(keep_max)
        self.purgeArchivedRevisions(keep_max)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url()+'/manage_repoInfo'
                                      '?manage_tabs_message=Purged.&details=1')

    security.declareProtected(ManagePortal, 'manage_purgeDeletedRevisions')
    def manage_purgeDeletedRevisions(self, REQUEST=None):
        """Purge revisions for deleted docids."""
        self.purgeDeletedRevisions()
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url()+'/manage_repoInfo'
                                      '?manage_tabs_message=Purged.&details=1')


    # XXX security?
    security.declarePublic('manage_redirectRevision')
    def manage_redirectRevision(self, docid, rev, RESPONSE):
        """Redirect to the object for a docid+rev."""
        ob = self.getObjectRevision(docid, rev)
        RESPONSE.redirect(ob.absolute_url()+'/manage_workspace')


InitializeClass(ObjectRepositoryTool)


# Create a workflow configuration object that denies any workflow
setattr(ObjectRepositoryTool, Config_id,
        NoWorkflowConfiguration())
# security.declarePrivate(...)
setattr(ObjectRepositoryTool, Config_id+'__roles__', ())

