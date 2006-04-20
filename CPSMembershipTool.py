# (C) Copyright 2002-2005 Nuxeo SARL <http://nuxeo.com>
# Authors:
# Florent Guillaume <fg@nuxeo.com>
# Alexandre Fernandez <alex@nuxeo.com>
# Julien Anguenot <ja@nuxeo.com>
# M.-A. Darche <madarche@nuxeo.com>
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
#
# Replace MonkeyPatch of Membershiptool by real object use
#
# $Id$

import sys

# python sets from 2.3 onward
try: set
except NameError: from sets import Set as set

from types import StringType
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo
from AccessControl import Unauthorized
from AccessControl import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from AccessControl.User import nobody
from AccessControl.User import UnrestrictedUser
from Acquisition import aq_base, aq_parent, aq_inner
from ZODB.POSException import ConflictError

from zope.interface import implements
from Products.CMFCore.interfaces import IMembershipTool

from Products.CMFCore.permissions import View, ManagePortal
from Products.CMFCore.permissions import ListPortalMembers
from AccessControl.Permissions import manage_users as ManageUsers
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFDefault.MembershipTool import MembershipTool
from Products.CMFCore.MemberDataTool import MemberDataTool

from Products.CPSUtil.id import generateId
from utils import mergedLocalRoles, mergedLocalRolesWithPath

from zLOG import LOG, DEBUG, PROBLEM, ERROR


class CPSUnrestrictedUser(UnrestrictedUser):
    """Unrestricted user that still has an id."""
    def getId(self):
        """Return the ID of the user."""
        return self.getUserName()


class CPSMembershipTool(MembershipTool):
    """ Replace MonkeyPatch of Membershiptool by real object use."""

    implements(IMembershipTool)

    _actions = ()

    meta_type = 'CPS Membership Tool'

    _properties = (
        {'id': 'membersfolder_id', 'type': 'string', 'mode': 'w',
         'label': 'Members folder relative path'},
        {'id': 'memberareaCreationFlag', 'type': 'boolean', 'mode': 'w',
         'label': 'Member folder created at login'},
        {'id': 'memberfolder_portal_type', 'type': 'string', 'mode': 'w',
         'label': 'Member folder portal type'},
        {'id': 'memberfolder_roles', 'type': 'tokens', 'mode': 'w',
         'label': 'Member folder owner local roles'},
        {'id': 'pending_members', 'type': 'lines', 'mode': 'w',
         'label': 'Recently deleted members'},
        )
    memberareaCreationFlag = True
    membersfolder_id = 'Members'
    memberfolder_portal_type = 'Folder'
    memberfolder_roles = ('Owner',)
    pending_members = ()


    # XXX this is slightly better than what was done before (hardcoded roles
    # in each method) as this one centralises the allowed roles declaration
    # and thus makes it possible to easily monkey-patch it. Would nethertheless
    # be more elegant to provide an API for changing roles that can manage
    # local roles (with proper permissions on methods of this API)
    roles_managing_local_roles = ('WorkspaceManager', 'SectionManager')

    security = ClassSecurityInfo()

    security.declarePublic('assertViewable')
    def assertViewable(self, context):
        """Raise Unauthorized if member doesn't have the View permission."""

        if not _checkPermission(View, context):
            raise Unauthorized

    security.declarePublic('canMemberChangeLocalRoles')
    def canMemberChangeLocalRoles(self, context):
        """Can the authenticated member change the local roles
        """
        user = getSecurityManager().getUser()
        return (user.has_role('Manager') or
                user.has_role(self.roles_managing_local_roles, context))

    security.declareProtected(View, 'getMergedLocalRoles')
    def getMergedLocalRoles(self, object, withgroups=1):
        """Return aquisition roles"""
        return mergedLocalRoles(object, withgroups)

    security.declareProtected(View, 'getMergedLocalRolesWithPath')
    def getMergedLocalRolesWithPath(self, object, withgroups=1):
        """Return aquisition roles with path"""
        return mergedLocalRolesWithPath(object, withgroups)

    security.declareProtected(View, 'getCPSCandidateLocalRoles')
    def getCPSCandidateLocalRoles(self, obj):
        """What local roles according to the context ?"""

        member = self.getAuthenticatedMember()
        roles = member.getRolesInContext(obj)
        has_proper_role = 0
        for r in self.roles_managing_local_roles:
            if r in roles:
                has_proper_role = 1
                break
        if has_proper_role or 'Manager' in roles:
            return self.getPortalRoles()
        else:
            member_roles = [role for role in roles
                            if role not in ('Member', 'Authenticated')]
            member_roles.sort()
            return member_roles

    security.declareProtected(View, 'setLocalRoles')
    def setLocalRoles(self, obj, member_ids, member_role, reindex=1):
        """ Set local roles on an item """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        has_proper_role = 0
        for r in self.roles_managing_local_roles:
            if r in my_roles:
                has_proper_role = 1
                break
        if has_proper_role or 'Manager' in my_roles or member_role in my_roles:
            for member_id in member_ids:
                roles = list(obj.get_local_roles_for_userid(userid=member_id))
                if member_role not in roles:
                    roles.append(member_role)
                    obj.manage_setLocalRoles(member_id, roles)

        if reindex:
            # It is assumed that all objects have the method
            # reindexObjectSecurity, which is in CMFCatalogAware and
            # thus PortalContent and PortalFolder.
            obj.reindexObjectSecurity()

    security.declarePrivate('_deleteLocalRoles')
    def _deleteLocalRoles(self, obj, member_ids, member_role=''):
        """Delete local roles or member_role  on obj for member_ids
        """
        if not member_role:
            obj.manage_delLocalRoles(userids=member_ids)
        else:
            for member_id in member_ids:
                current_roles = list(obj.get_local_roles_for_userid(
                    userid=member_id))
                new_roles = [role for role in current_roles
                             if role != member_role]
                obj.manage_delLocalRoles(userids=[member_id])
                if new_roles:
                    obj.manage_setLocalRoles(member_id, new_roles)

    security.declareProtected(View, 'deleteLocalRoles')
    def deleteLocalRoles(self, obj, member_ids, reindex=1, recursive=0,
                         member_role=''):
        """ Delete local roles for members member_ids """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        has_proper_role = 0
        for r in self.roles_managing_local_roles:
            if r in my_roles:
                has_proper_role = 1
                break

        if has_proper_role or 'Manager' in my_roles or 'Owner' in my_roles:
            self._deleteLocalRoles(obj, member_ids, member_role)

        if recursive:
            path = '/'.join(obj.getPhysicalPath())
            user_ids = ['user:%s' % id for id in member_ids]
            portal_catalog = getToolByName(self, 'portal_catalog')
            results = portal_catalog(cps_filter_sets='searchable', path=path,
                                     localUsersWithRoles=user_ids)
            for brain in results:
                ob = brain.getObject()
                self._deleteLocalRoles(ob, member_ids, member_role)
        if reindex:
            obj.reindexObjectSecurity()


    security.declareProtected(View, 'setLocalGroupRoles')
    def setLocalGroupRoles(self, obj, ids, role, reindex=1):
        """Set local group roles on an item."""
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        has_proper_role = 0
        for r in self.roles_managing_local_roles:
            if r in my_roles:
                has_proper_role = 1
                break
        if has_proper_role or 'Manager' in my_roles or role in my_roles:
            for id in ids:
                roles = list(obj.get_local_roles_for_groupid(id))
                if role not in roles:
                    roles.append(role)
                    obj.manage_setLocalGroupRoles(id, roles)
        if reindex:
            obj.reindexObjectSecurity()

    security.declareProtected(View, 'deleteLocalGroupRoles')
    def deleteLocalGroupRoles(self, obj, ids, role=None, reindex=1):
        """Delete local group roles for members ids.

        If role is None, delete all roles, otherwise delete only this one.
        Never deletes the roles a user doesn't already have,
        unless he is a Manager (or has a "managing role").

        Returns a boolean saying if something changed.
        """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        if 'Manager' in my_roles:
            has_managing_role = 1
        else:
            has_managing_role = 0
            for r in self.roles_managing_local_roles:
                if r in my_roles:
                    has_managing_role = 1
                    break
        if role is None:
            if has_managing_role:
                removed_roles = None # all
            else:
                removed_roles = my_roles
        else:
            if has_managing_role or role in my_roles:
                removed_roles = [role]
            else:
                # Cannot change anything
                return 0
        changed = 0
        for id in ids:
            current_roles = list(obj.get_local_roles_for_groupid(id))
            if removed_roles is None: # all
                roles = []
            else:
                roles = [r for r in current_roles if r not in removed_roles]
            if roles != current_roles:
                changed = 1
                if roles:
                    obj.manage_setLocalGroupRoles(id, roles)
                else:
                    obj.manage_delLocalGroupRoles([id])
        if changed and reindex:
            obj.reindexObjectSecurity()
        return changed

    security.declareProtected(ManagePortal, 'setMembersFolderById')
    def setMembersFolderById(self, id=''):
        """Set the members folder object by its relative path."""
        rpath = id.strip()
        if rpath.startswith('/') or rpath.startswith('.'):
            raise ValueError("Illegal relative path '%s'" % rpath)
        self.membersfolder_id = rpath

    security.declarePublic('getMembersFolder')
    def getMembersFolder(self):
        """Get the members folder object.

        Its location (portal-relative path) is stored in the variable
        membersfolder_id.
        """
        parent = aq_parent(aq_inner(self))
        members = parent.unrestrictedTraverse(self.membersfolder_id,
                                              default=None)
        return members

    security.declareProtected(ManageUsers, 'deleteMemberArea')
    def deleteMemberArea(self, member_id):
        """Delete member area of member specified by member_id."""
        members = self.getMembersFolder()
        if not members:
            return 0
        if hasattr(aq_base(members), member_id):
            members.manage_delObjects(member_id)
            return 1
        else:
            return 0

    # Based on CVS 1.5 (HEAD) method.
    security.declarePublic(ManagePortal, 'createMemberArea')
    def createMemberArea(self, member_id=''):
        """Create a member area for member_id or authenticated user.

        Called during login phase to create missing member areas.
        """

        if not self.getMemberareaCreationFlag():
            return None
        members = self.getMembersFolder()
        if not members:
            return None
        if self.isAnonymousUser():
            return None
        # Note: We can't use getAuthenticatedMember() and getMemberById()
        # because they might be wrapped by MemberDataTool.
        user = _getAuthenticatedUser(self)
        user_id = user.getId()
        if not member_id:
            member_id = user_id

        if member_id == user_id and self.isHomeless():
            # Check if authenticated user is homeless.
            return None

        member_area_id = self.getHomeFolderId(member_id)
        if hasattr(aq_base(members), member_area_id):
            return None
        if member_id == user_id:
            member = user
        else:
            if _checkPermission(ManageUsers, self):
                member = self.acl_users.getUserById(member_id, None)
                if member:
                    member = member.__of__(self.acl_users)
                else:
                    raise ValueError("Member %s does not exist" % member_id)
            else:
                return None

        # Setup a temporary security manager so that creation is not
        # hampered by insufficient roles.

        # Use member_id so that the Owner role is set for it.
        tmp_user = CPSUnrestrictedUser(member_id, '',
                                       ['Manager', 'Member'], '')
        tmp_user = tmp_user.__of__(self.acl_users)
        old_sm = getSecurityManager()
        newSecurityManager(None, tmp_user)

        try:
            # Create member area.
            members.invokeFactory(self.memberfolder_portal_type,
                                  member_area_id)
            member_area = members._getOb(member_area_id)
            # TODO set workspace properties ? title ..
            member_area.changeOwnership(member)
            member_area.manage_setLocalRoles(member_id,
                                             list(self.memberfolder_roles))
            member_area.reindexObjectSecurity()

            self._createMemberContentAsManager(member, member_id, member_area)

        finally:
            # Revert to original user.
            setSecurityManager(old_sm)

        self._createMemberContent(member, member_id, member_area)

        self._notifyMemberAreaCreated(member, member_id, member_area)

    security.declarePublic('createMemberarea')
    createMemberarea = createMemberArea

    # Can be overloaded by subclasses.
    security.declarePrivate('_createMemberContentAsManager')
    def _createMemberContentAsManager(self, member, member_id, member_folder):
        """Create the content of the member area.

        Executed with Manager privileges.
        """
        pass

    # Can be overloaded by subclasses.
    security.declarePrivate('_createMemberContent')
    def _createMemberContent(self, member, member_id, member_folder):
        """Create the content of the member area."""
        # Member is in fact a user object, it's not wrapped in the
        # memberdata tool.
        # Create Member's initial content, skinnable.
        if hasattr(self, 'createMemberContent'):
            self.createMemberContent(member=member,
                                     member_id=member_id,
                                     member_folder=member_folder)

    # Can be overloaded by subclasses.
    security.declarePrivate('_notifyMemberAreaCreated')
    def _notifyMemberAreaCreated(self, member, member_id, member_folder):
        """Perform special actions after member area has been created
        """
        pass

    security.declarePublic('isHomeless')
    def isHomeless(self, member=None):
        """Return 1 if member have no home using homeless attribute.

        Anonymous users and users registered above CPS level are homeless.
        """
        ret = 0
        if member is None:
            member = self.getAuthenticatedMember()
        if member.getUserName() == "Anonymous User":
            return 1
        # users registered above the portal level are homeless
        member_acl_users = aq_parent(aq_inner(member.getUser()))
        if aq_base(member_acl_users) is not aq_base(self.acl_users):
            return 1

        if hasattr(member, 'getProperty'):
            ret = member.getProperty('homeless', 0)
            if ret and ret != '0':
                ret = 1
            else:
                ret = 0

        return ret

    # Overloaded to do folder access through _getOb.
    security.declarePublic('getHomeFolder')
    def getHomeFolder(self, id=None, verifyPermission=0):
        """Return a member's home folder object, or None."""
        member = self.getAuthenticatedMember()
        if not hasattr(member, 'getMemberId'):
            return None

        member_id = member.getMemberId()
        if id is None:
            id = member_id

        if id == member_id and self.isHomeless(member=member):
            # Check if authenticated user is homeless.
            return None

        members = self.getMembersFolder()
        if members:
            try:
                member_area_id = self.getHomeFolderId(id)
                folder = members._getOb(member_area_id)
                if verifyPermission and not _checkPermission(View, folder):
                    # Don't return the folder if the user can't get to it.
                    return None
                return folder
            except (AttributeError, TypeError, KeyError):
                pass
        return None

    security.declarePublic('getHomeFolderId')
    def getHomeFolderId(self, id, max_chars_for_id=128):
        """Compute an home folder id for the given member id."""
        id = generateId(id, max_chars_for_id, False)
        return id

    security.declarePublic('homeFolderExists')
    def homeFolderExists(self, id):
        """"""
        members = self.getMembersFolder()
        if members:
            try:
                member_area_id = self.getHomeFolderId(id)
                folder = members._getOb(member_area_id)
                return 1
            except (AttributeError, KeyError):
                return 0

    security.declarePrivate('listActions')
    def listActions(self, info=None, object=None):
        """List actions available through the tool."""
        return self._actions

    # We redefine this to fix a security declaration problem in CMF <= 1.4.1.
    security.declareProtected(ListPortalMembers, 'searchMembers')
    def searchMembers(self, search_param, search_term):
        """Search the membership."""
        return MembershipTool.searchMembers(self, search_param, search_term)

    # Bugfix included in 1.4 branch and HEAD of CMF:
    security.declarePrivate('wrapUser')
    def wrapUser(self, u, wrap_anon=0):
        """Set up the correct acquisition wrappers for a user object.

        Provides an opportunity for a portal_memberdata tool to retrieve and
        store member data independently of the user object.
        """
        b = getattr(u, 'aq_base', None)
        if b is None:
            # u isn't wrapped at all.  Wrap it in self.acl_users.
            b = u
            u = u.__of__(self.acl_users)
        if (b is nobody and not wrap_anon) or hasattr(b, 'getMemberId'):
            # This user is either not recognized by acl_users or it is
            # already registered with something that implements the
            # member data tool at least partially.
            return u

        # Apply any role mapping if we have it
        if hasattr(self, 'role_map'):
            for portal_role in self.role_map.keys():
                if (self.role_map.get(portal_role) in u.roles and
                        portal_role not in u.roles):
                    u.roles.append(portal_role)

        mdtool = getToolByName(self, 'portal_memberdata', None)
        if mdtool:
            try:
                u = mdtool.wrapUser(u)
            except ConflictError: # Bugfix
                raise
            except:
                LOG('CPSCore.CPSMembershipTool', ERROR,
                    'Error during wrapUser', error=sys.exc_info())
        return u

    # CMF 1.5 method plus check_permission argument
    security.declareProtected(ManageUsers, 'deleteMembers')
    def deleteMembers(self, member_ids, delete_memberareas=1,
                      delete_localroles=0, check_permission=1):
        """Delete members specified by member_ids.

        XXX does not call local roles deletion by default but stores their
        ids in the pending_members property. Use purgeDeletedMembersLocalRoles()
        to delete them
        """

        # Delete members in acl_users.
        acl_users = self.acl_users
        # Don't know why CMF needs to check permission here ?
        if check_permission and not _checkPermission(ManageUsers, acl_users):
            raise Unauthorized("You need the 'Manage users' "
                               "permission for the underlying User Folder.")
        else:
            if type(member_ids) is StringType:
                member_ids = (member_ids,)
            member_ids = list(member_ids)
            for member_id in member_ids[:]:
                if not acl_users.getUserById(member_id, None):
                    member_ids.remove(member_id)
            if hasattr(acl_users, '_doDelUsers'):
                acl_users._doDelUsers(member_ids)
            else:
                try:
                    acl_users.userFolderDelUsers(member_ids)
                except (NotImplementedError, 'NotImplemented'):
                    raise NotImplementedError(
                        "The underlying User Folder "
                        "doesn't support deleting members.")

        # Delete member data in portal_memberdata.
        mdtool = getToolByName(self, 'portal_memberdata', None)
        if mdtool:
            for member_id in member_ids:
                mdtool.deleteMemberData(member_id)

        # Delete members' home folders including all content items.
        if delete_memberareas:
            for member_id in member_ids:
                self.deleteMemberArea(member_id)

        # Delete members' local roles.
        if delete_localroles:
            utool = getToolByName(self, 'portal_url')
            self.deleteLocalRoles(utool.getPortalObject(), member_ids,
                                  reindex=1, recursive=1)
        # Or stores their ids in the pending_members property for a
        # delayed purge
        else:
            already_pending =  set(self.getProperty('pending_members'))
            self.pending_members = tuple(already_pending.union(member_ids))

        return tuple(member_ids)

    security.declareProtected(ManageUsers, 'purgeDeletedMembersLocalRoles')
    def purgeDeletedMembersLocalRoles(self):
        """Trigger the purge of localroles of member_ids stored in
        pending_members

        return the list of ids that where cleaned

        WARNING: This can take a while (security reindexing)
        """
        # Remove duplicates
        pending_members = set(self.getProperty('pending_members'))

        # Filter out the member_ids that correspond to actual members
        member_ids = self.listMemberIds()
        pending_members = [id for id in pending_members if id not in member_ids]

        # Purge
        utool = getToolByName(self, 'portal_url')
        self.deleteLocalRoles(utool.getPortalObject(), pending_members,
                reindex=1, recursive=1)

        # Updating the pending_members property
        self.pending_members = ()

        return pending_members

    #
    #   ZMI interface methods
    #

    # Override configuration screen for adding local roles cleaning.
    security.declareProtected(ManagePortal, 'manage_mapRoles')
    manage_mapRoles = DTMLFile('zmi/membershipRolemapping', globals())

    security.declareProtected(ManagePortal, 'manage_deleteLocalRoles')
    def manage_deleteLocalRoles(self, member_ids, REQUEST=None):
        """Basically call 'deleteLocalRoles' the way 'deleteMembers' used to do
           by default.
        """
        if member_ids:
            utool = getToolByName(self, 'portal_url')
            self.deleteLocalRoles(utool.getPortalObject(), member_ids,
                                  reindex=1, recursive=1)
            message = 'Ids %s cleaned.' % member_ids
        else:
            message = 'No id given.'

        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/manage_mapRoles' +
                                      '?manage_tabs_message=%s' % message)

    security.declareProtected(ManagePortal, 'manage_purgeLocalRoles')
    def manage_purgeLocalRoles(self, REQUEST=None):
        """Call 'purgeDeletedMembersLocalRoles' to clean localroles for ids
        stored in the pending_members property
        """
        ids = self.purgeDeletedMembersLocalRoles()
        if ids:
            message = "Ids %s cleaned." % ids
        else:
            message = "No member id to clean"

        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(self.absolute_url() +
                                      '/manage_mapRoles' +
                                      '?manage_tabs_message=%s' % message)


InitializeClass(CPSMembershipTool)

def addCPSMembershipTool(dispatcher, **kw):
    """Add a membership tool"""
    mt = CPSMembershipTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)


#
# Patch MemberDataTool to be sure it has a deleteMemberData method
#

def deleteMemberData(self, member_id):
    """Delete member data of specified member."""
    members = self._members
    if members.has_key(member_id):
        del members[member_id]
        return 1
    else:
        return 0

MemberDataTool.deleteMemberData = deleteMemberData
MemberDataTool.deleteMemberData__roles__ = () # Private
