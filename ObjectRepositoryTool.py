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

from zLOG import LOG, ERROR, DEBUG
import sys
import random
from types import TupleType, ListType
from Globals import InitializeClass
from Acquisition import aq_base
from AccessControl import ClassSecurityInfo
from AccessControl.Permission import Permission, name_trans

from OFS.CopySupport import CopyError

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.PortalFolder import PortalFolder
from Products.DCWorkflow.utils import modifyRolesForPermission

from Products.NuxCPS3.CPSWorkflowTool import CPSWorkflowConfig_id
from Products.NuxCPS3.CPSTypes import TypeConstructor, TypeContainer


class NoWorkflowConfiguration:
    """Class for a workflow configuration object that denies
    all workflows."""

    security = ClassSecurityInfo()

    security.declarePrivate('getPlacefulChainFor')
    def getPlacefulChainFor(self, portal_type, start_here=None):
        """No workflow chain is allowed."""
        return ()

InitializeClass(NoWorkflowConfiguration)


def set_local_roles_with_groups(ob, lroles):
    """Set all the local roles and group local roles.

    Return True if something was changed.
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
    uroles = ob.__ac_local_roles__ or {}
    groles = ob.__ac_local_group_roles__ or {}
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


# XXX we'll want a btreefolder2 here, not a folder
class ObjectRepositoryTool(UniqueObject, PortalFolder,
                           TypeConstructor, TypeContainer):
    """An object repository stores objects that can be
    available in several versions.

    It can be queried for the best version of a given object matching
    a set of constraints, for instance on language.

    repoid is an identifier unique to the repository that describes a set
    of versions of one object.
    """

    id = 'portal_repository'
    meta_type = 'CPS Repository Tool'
    portal_type = meta_type

    security = ClassSecurityInfo()

    def __init__(self):
        pass

    #
    # API
    #

    security.declarePrivate('invokeFactory')
    def invokeFactory(self, type_name,
                      repoid=None, version_info=None,
                      *args, **kw):
        """Create an object with repoid and version in the repository.

        If repoid is None, a new one is generated
        If version_info is None, 1 is used.
        Returns the used repoid and version.

        (Called by the proxy tool.)
        """
        if version_info is None:
            version_info = 1
        if repoid is None:
            while 1:
                repoid = str(random.randrange(1,2147483600))
                id = self._get_id(repoid, version_info)
                if not hasattr(self, id):
                    break
        else:
            id = self._get_id(repoid, version_info)
            if hasattr(self, id):
                raise ValueError('A document with repoid=%s and version=%s '
                                 'already exists' % (repoid, version_info))
        self.constructContent(type_name, id, *args, **kw)
        return (repoid, version_info)

    security.declarePrivate('delObjectVersion')
    def delObjectVersion(self, repoid, version_info):
        """Delete a version of an object."""
        id = self._get_id(repoid, version_info)
        self._delObject(id)

    security.declarePrivate('getObjectVersion')
    def getObjectVersion(self, repoid, version_info):
        """Get a version of an object."""
        id = self._get_id(repoid, version_info)
        try:
            return self._getOb(id)
        except AttributeError:
            LOG('ObjectRepositoryTool', ERROR,
                'getObjectVersion: no object %s' % repoid)
            return None

    security.declarePrivate('delObject')
    def delObject(self, repoid):
        """Delete all the versions of an object."""
        prefix = self._get_id_prefix(repoid)
        for id in self.objectIds():
            if id.startswith(prefix):
                self._delObject(id)

    security.declarePrivate('listAll')
    def listAll(self):
        """List all (repoid, version_info) in the repository."""
        items = []
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            items.append((repoid, version_info))
        return items

    security.declarePrivate('listRepoIds')
    def listRepoIds(self):
        """List all the repoids in the repository."""
        idd = {}
        has = idd.has_key
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            if has(repoid):
                continue
            idd[repoid] = None
        return idd.keys()

    security.declarePrivate('listVersions')
    def listVersions(self, repoid):
        """List all the versions of a given object."""
        rid = repoid
        version_infos = []
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            if rid != repoid:
                continue
            version_infos.append(version_info)
        return version_infos

    security.declarePublic('getRepoIdAndVersionFromId')
    def getRepoIdAndVersionFromId(self, id):
        """Get repoid and version_info from an id."""
        if hasattr(self, id):
            return self._split_id(id)
        else:
            return (None, None)

    security.declarePrivate('freezeVersion')
    def freezeVersion(self, repoid, version_info):
        """Freeze a version of a document.

        Any modification to a frozen version should be forbidden by the
        rest of the system.

        There's no way to unfreeze a version without cloning it.

        (Called by ProxyTool.)
        """
        ob = self.getObjectVersion(repoid, version_info)
        # Don't write to ZODB if already frozen.
        if not getattr(aq_base(ob), '_cps_frozen', 0):
            ob._cps_frozen = 1
            # Unacquire modification permission.
            modifyRolesForPermission(ob, ModifyPortalContent, ('Manager',))

    security.declarePrivate('isVersionFrozen')
    def isVersionFrozen(self, repoid, version_info):
        """Is a version frozen?"""
        ob = self.getObjectVersion(repoid, version_info)
        return getattr(ob, '_cps_frozen', 0)

    security.declarePrivate('copyVersion')
    def copyVersion(self, repoid, version_info):
        """Copy a version of an object into a new version.

        Return the newly created (unfrozen) version.
        """
        ob = self.getObjectVersion(repoid, version_info)
        newv = version_info + 1
        while 1:
            # Find a free version
            newid = self._get_id(repoid, newv)
            if not hasattr(self, newid):
                break
            newv += 1
        newob = self.copyContent(ob, newid)
        if hasattr(newob, '_cps_frozen'):
            delattr(newob, '_cps_frozen')
        # Reset (acquire) modification permission.
        modifyRolesForPermission(newob, ModifyPortalContent, [])
        # XXX add some info to the history
        return newv

    security.declarePrivate('getUnfrozenVersion')
    def getUnfrozenVersion(self, repoid, version_info):
        """Return the version of an unfrozen version of an object.

        (Called by ProxyTool.)
        """
        ob = self.getObjectVersion(repoid, version_info)
        if not getattr(aq_base(ob), '_cps_frozen', 0):
            return version_info
        newv = self.copyVersion(repoid, version_info)
        return newv

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
                    roles = p.getRoles(default=[])
                    if role not in roles:
                        r = list(roles)+[role]
                        if type(roles) is TupleType:
                            r = tuple(r)
                        p.setRoles(r)
                    break
        return role

    security.declarePrivate('setObjectSecurity')
    def setObjectSecurity(self, repoid, version_info, userperms):
        """Set the security on an object.

        userperms is a dict of {user: [sequence of permissions]}
        user is user:uid or group:gid

        (Called by ProxyTool.)
        """
        LOG('obrep', DEBUG, 'setObjectSecurity repoid=%s v=%s perms=%s' %
            (repoid, version_info, userperms))
        ob = self.getObjectVersion(repoid, version_info)
        lroles = {}
        for user, perms in userperms.items():
            roles = [self.getPermissionRole(perm) for perm in perms]
            lroles[user] = roles
        changed = set_local_roles_with_groups(ob, lroles)
        if changed:
            ob.reindexObjectSecurity()

    #
    # Misc
    #

    def _get_id_prefix(self, repoid):
        return '%s__' % repoid

    def _get_id(self, repoid, version_info):
        id = '%s__%04d' % (repoid, version_info)
        return id

    def _split_id(self, id):
        try:
            repoid, version_info = id.split('__')
            version_info = int(version_info)
        except ValueError:
            LOG('ObjectRepositoryTool', ERROR, 'Cannot split id %s' % id)
            return (None, None)
        return (repoid, version_info)

    #
    # Forbid any workflow
    #

    # This done later by using setattr because the id is variable
    #.cps_workflow_configuration = NoWorkflowConfiguration()

    #
    # ZMI
    #

    manage_options = PortalFolder.manage_options

    # XXX security?
    security.declarePublic('manage_redirectVersion')
    def manage_redirectVersion(self, repoid, version, RESPONSE):
        """Redirect to the object for a repoid+version."""
        ob = self.getObjectVersion(repoid, version)
        RESPONSE.redirect(ob.absolute_url()+'/manage_workspace')


InitializeClass(ObjectRepositoryTool)


# Create a workflow configuration object that denies any workflow
setattr(ObjectRepositoryTool, CPSWorkflowConfig_id,
        NoWorkflowConfiguration())
# security.declarePrivate(...)
setattr(ObjectRepositoryTool, CPSWorkflowConfig_id+'__roles__', ())

