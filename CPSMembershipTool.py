# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Authors: Florent Guillaime <fg@nuxeo.com>
#          Alexandre Fernandez <alex@nuxeo.com>
#
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


from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFCore.CMFCorePermissions import View
from Products.CMFDefault.MembershipTool import MembershipTool
from Products.NuxUserGroups.CatalogToolWithGroups import mergedLocalRoles

class CPSMembershipTool(MembershipTool):

    meta_type = 'CPS Membership Tool'

    security = ClassSecurityInfo()
    
    security.declareProtected(View, 'getMergedLocalRoles')
    def getMergedLocalRoles(self, object, withgroups=1):
        """
        return aquisition roles
        """
        return mergedLocalRoles(object, withgroups)

    security.declareProtected(View, 'setLocalGroupRoles')
    def setLocalGroupRoles(self, obj, ids, role, reindex=1):
        """Set local group roles on an item."""
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        if 'Manager' in my_roles or role in my_roles:
            for id in ids:
                roles = list(obj.get_local_roles_for_groupid(id))
                if role not in roles:
                    roles.append(role)
                    obj.manage_setLocalGroupRoles(id, roles)
        if reindex:
            obj.reindexObjectSecurity()

    security.declareProtected(View, 'deleteLocalGroupRoles')
    def deleteLocalGroupRoles(self, obj, ids, reindex=1):
        """Delete local group roles for members member_ids."""
        member = self.getAuthenticatedMember()
        my_roles = member.getRolesInContext(obj)
        if 'Manager' in my_roles:
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
    
InitializeClass(MembershipTool)

    
    
def addCPSMembershipTool(dispatcher, **kw):
    """
    add a membership tool
    """
    mt = CPSMembershipTool(**kw)
    id = mt.getId()
    container = dispatcher.Destination()
    container._setObject(id, mt)
    mt = container._getOb(id)
