# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Authors: Florent Guillaume <fg@nuxeo.com>
#          Alexandre Fernandez <alex@nuxeo.com>
#          Julien Anguenot <ja@nuxeo.com>
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
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.User import nobody
from AccessControl.User import UnrestrictedUser
from Acquisition import aq_base, aq_parent, aq_inner
from ZODB.POSException import ConflictError

from Products.CMFCore.CMFCorePermissions import View, ManagePortal
from Products.CMFCore.CMFCorePermissions import ListPortalMembers
from AccessControl.Permissions import manage_users as ManageUsers
from Products.CMFCore.ActionsTool import ActionInformation as AI
from Products.CMFCore.Expression import Expression
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFDefault.MembershipTool import MembershipTool

from Products.CPSCore.utils import mergedLocalRoles, mergedLocalRolesWithPath

from zLOG import LOG, DEBUG, ERROR

# XXX : to move somewhere else
WORKSPACES = "workspaces"
MEMBERS = "members"


class CPSUnrestrictedUser(UnrestrictedUser):
    """Unrestricted user that still has an id."""
    def getId(self):
        """Return the ID of the user."""
        return self.getUserName()


class CPSMembershipTool(MembershipTool):
    """ Replace MonkeyPatch of Membershiptool by real object use."""

    #
    # Actions for CPS
    #
    _actions = [
      AI(id='login',
         title='Login',
         description='Click here to Login',
         action=Expression(text='string:${portal_url}/login_form'),
         permissions=(View,),
         category='user',
         condition=Expression(text='not: member'),
         visible=1),
      AI(id='logout',
         title='Log out',
         description='Click here to logout',
         action=Expression(text='string:${portal_url}/logout'),
         permissions=(View,),
         category='user',
         condition=Expression(text='member'),
         visible=1),
      AI(id='mystuff',
         title='My stuff',
         description='Goto your home folder',
         action=Expression(text='string:${portal/portal_membership'
                           + '/getHomeUrl}/folder_contents'),
         permissions=(View,),
         category='user',
         condition=Expression(text='python: member and '
                              + 'portal.portal_membership.getHomeFolder()'),
         visible=1)
    ]

    meta_type = 'CPS Membership Tool'

    membersfolder_id = 'workspaces/members'
    memberfolder_portal_type = 'Workspace'
    memberfolder_roles = ('Owner', 'WorkspaceManager')

    security = ClassSecurityInfo()

    security.declareProtected(View, 'getMergedLocalRoles')
    def getMergedLocalRoles(self, object, withgroups=1):
        """Return aquisition roles"""
        return mergedLocalRoles(object, withgroups)

    security.declareProtected(View, 'getMergedLocalRolesWithPath')
    def getMergedLocalRolesWithPath(self, object, withgroups=1):
        """Return aquisition roles with path"""
        return mergedLocalRolesWithPath(object, withgroups)

    security.declareProtected(View, 'getCandidateLocalRoles')
    def getCPSCandidateLocalRoles(self, obj):
        """What local roles according to the context ?"""
        # XXX This code must change, it has knowledge of CPSDefault.
        member = self.getAuthenticatedMember()
        roles = member.getRolesInContext(obj)
        if 'WorkspaceManager' in roles or\
           'SectionManager' in roles or\
           'Manager' in roles:
            return self.getPortalRoles()
        else:
            member_roles = [role for role in roles
                            if role not in ('Member', 'Authenticated')]
            member_roles.sort()
            return tuple(member_roles)

    security.declareProtected(View, 'setLocalRoles')
    def setLocalRoles(self, obj, member_ids, member_role, reindex=1):
        """ Set local roles on an item """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        # XXX This code must change, it has knowledge of CPSDefault.
        if 'Manager' in my_roles or \
               'WorkspaceManager' in my_roles or \
               'SectionManager' in my_roles or \
               member_role in my_roles:
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

    security.declareProtected(View, 'deleteLocalRoles')
    def deleteLocalRoles(self, obj, member_ids, reindex=1):
        """ Delete local roles for members member_ids """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)

        if 'Manager' in my_roles or 'Owner' in my_roles or \
               'WorkspaceManager' in my_roles or \
               'SectionManager' in my_roles:
            obj.manage_delLocalRoles(userids=member_ids)

        if reindex:
            obj.reindexObjectSecurity()

    security.declareProtected(View, 'setLocalGroupRoles')
    def setLocalGroupRoles(self, obj, ids, role, reindex=1):
        """Set local group roles on an item."""
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        if 'Manager' in my_roles or \
               'WorkspaceManager' in my_roles or \
               'SectionManager' in my_roles or \
               role in my_roles:
            for id in ids:
                roles = list(obj.get_local_roles_for_groupid(id))
                if role not in roles:
                    roles.append(role)
                    obj.manage_setLocalGroupRoles(id, roles)
        if reindex:
            obj.reindexObjectSecurity()

    security.declareProtected(View, 'deleteLocalGroupRoles')
    def deleteLocalGroupRoles(self, obj, ids, role, reindex=1):
        """Delete local group roles for members member_ids."""
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        if 'Manager' in my_roles or \
           'WorkspaceManager' in my_roles or \
           'SectionManager' in my_roles or \
           role in my_roles:
            obj.manage_delLocalGroupRoles(ids)
        else:
            # Only remove the roles we have.
            for id in ids:
                roles = obj.get_local_roles_for_groupid(id)
                roles = [r for r in roles if r not in my_roles]
                if roles:
                    obj.manage_setLocalGroupRoles(id, roles)
                else:
                    obj.manage_delLocalGroupRoles([id])
        if reindex:
            obj.reindexObjectSecurity()

    security.declareProtected(ManagePortal, 'setMembersFolderById')
    def setMembersFolderById(self, id=''):
        """Set the members folder object by its relative path."""
        rpath = id.strip()
        if rpath.startwith('/') or rpath.startswith('.'):
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
        if hasattr(aq_base(members), member_id):
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
        newSecurityManager(None, tmp_user)

        # Create member area.
        members.invokeFactory(self.memberfolder_portal_type, member_id)
        f = getattr(members, member_id)
        # TODO set workspace properties ? title ..
        f.changeOwnership(member)
        f.manage_setLocalRoles(member_id, list(self.memberfolder_roles))
        f.reindexObjectSecurity()

        # Rebuild the tree with corrected local roles.
        # This needs a user that can View the object.
        portal_eventservice = getToolByName(self, 'portal_eventservice')
        portal_eventservice.notify('sys_modify_security', f, {})

        # Revert to original user.
        newSecurityManager(None, user)

        self._createMemberContent(member, member_id, f)

    security.declarePublic('createMemberarea')
    createMemberarea = createMemberArea

    # Can be overloaded by subclasses.
    def _createMemberContent(self, member, member_id, member_folder):
        """Create the content of the member area."""
        # Member is in fact a user object, it's not wrapped in the
        # memberdata tool.
        portal_cpscalendar = getToolByName(self, 'portal_cpscalendar', None)
        if portal_cpscalendar:
            portal_cpscalendar.createMemberCalendar(member_id)

        # Create Member's initial content, skinnable.
        if hasattr(self, 'createMemberContent'):
            self.createMemberContent(member=member,
                                     member_id=member_id,
                                     member_folder=member_folder)


    security.declarePublic('getHomeFolder')
    def getHomeFolder(self, id=None, verifyPermission=0):
        """Return a member's home folder object, or None."""

        if id is None:
            member = self.getAuthenticatedMember()
            if not hasattr(member, 'getMemberId'):
                return None
            id = member.getMemberId()
        parent = self.aq_inner.aq_parent

        ws_root = getattr(parent, WORKSPACES, None)
        try:
            members = getattr(ws_root, MEMBERS, None)
            folder = getattr(members, id, None)
            if verifyPermission and not _checkPermission('View', folder):
                # Don't return the folder if the user can't get to it.
                return None
            return folder
        except KeyError:
            pass
        return None

    security.declarePrivate('listActions')
    def listActions(self, info=None):
        """List actions available through the tool."""
        return self._actions

    # We redefine this to fix a security declaration problem in CMF <= 1.4.1.
    security.declareProtected(ListPortalMembers, 'searchMembers')
    def searchMembers(self, search_param, search_term, *args, **kw):
        """Search the membership."""
        return MembershipTool.searchMembers(self, search_param, search_term,
                                            *args, **kw)

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

InitializeClass(MembershipTool)

def addCPSMembershipTool(dispatcher, **kw):
    """Add a membership tool"""
    mt = CPSMembershipTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)
