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

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.User import UnrestrictedUser

from Products.CMFCore.CMFCorePermissions import View, ManagePortal
from Products.CMFCore.ActionsTool import ActionInformation as AI
from Products.CMFCore.Expression import Expression
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import mergedLocalRoles
from Products.CMFDefault.MembershipTool import MembershipTool

from zLOG import LOG, DEBUG

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

    security = ClassSecurityInfo()

    security.declareProtected(View, 'getMergedLocalRoles')
    def getMergedLocalRoles(self, object, withgroups=1, withpath=0):
        """Return aquisition roles"""
        return mergedLocalRoles(object, withgroups, withpath)

    security.declareProtected(View, 'getCandidateLocalRoles')
    def getCPSCandidateLocalRoles(self, obj):
        """What local roles according to the context ?"""
        member = self.getAuthenticatedMember()
        roles = member.getRolesInContext(obj)
        if 'WorkspaceManager' in roles or\
           'SectionManager' in roles or\
           'Manager' in roles:
            return self.getPortalRoles()
        else:
            member_roles = list(roles)
            del member_roles[member_roles.index('Member')]
            return tuple(member_roles)

    security.declareProtected(View, 'setLocalRoles')
    def setLocalRoles(self, obj, member_ids, member_role, reindex=1):
        """ Set local roles on an item """
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)

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

    security.declareProtected(ManagePortal, 'createMemberarea')
    def createMemberarea(self, member_id):
        """Create a member area."""

        aclu = self.acl_users
        parent = self.aq_inner.aq_parent
        ws_root =  getattr(parent, WORKSPACES, None)
        members =  getattr(ws_root, MEMBERS, None)

        user = aclu.getUser(member_id)
        if user is not None:
            user = user.__of__(aclu)

        if members is not None and user is not None:
            f_title = "%s's Home" % member_id

            # Setup a temporary security manager so that creation is not
            # hampered by insufficient roles.
            old_user = getSecurityManager().getUser()
            # Use member_id so that the Owner role is set for it
            tmp_user = CPSUnrestrictedUser(member_id, '',
                                           ['Manager', 'Member'], '')
            tmp_user = tmp_user.__of__(aclu)
            newSecurityManager(None, tmp_user)

            members.invokeFactory('Workspace', member_id)

            f = getattr(members, member_id)
            # TODO set workspace properties ? title ..

            # Grant ownership to Member
            try:
                f.changeOwnership(user)
                # XXX this method is define in a testcase and just does a pass
            except AttributeError:
                pass  # Zope 2.1.x compatibility

            f.manage_setLocalRoles(member_id, ['Owner', 'WorkspaceManager'])

            # Rebuild the tree with corrected local roles.
            # This needs a user that can View the object.
            portal_eventservice = getToolByName(self, 'portal_eventservice')
            portal_eventservice.notify('sys_modify_security', f, {})

            newSecurityManager(None, old_user)



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

InitializeClass(MembershipTool)

def addCPSMembershipTool(dispatcher, **kw):
    """Add a membership tool"""
    mt = CPSMembershipTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)
