# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Jalon <jj@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
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

from zLOG import LOG, INFO, DEBUG

#
# Monkey patching starts here
#
# Patching UndoTool: Removing undo action
#

from Products.CMFCore.UndoTool import UndoTool

_actions = []
UndoTool._actions = _actions
LOG("CPSCore", INFO, "Patching CMFCore UndoTool : removing undo action")

## UndoToolPatch ends here

# Local role (group) support patches start here

from Products.CMFCore import utils
from Products.CMFCore.CatalogTool import IndexableObjectWrapper, \
     CatalogTool

LOG('CPSCore.utils', INFO, 'Patching CMF local role support')

def mergedLocalRoles(object, withgroups=0):
    LOG('CPSCore utils', DEBUG, 'mergedLocalRoles()')
    aclu = object.acl_users
    if hasattr(aclu, 'mergedLocalRoles'):
        return aclu.mergedLocalRoles(object, withgroups)
    return utils.old_mergedLocalRoles(object)

if not hasattr(utils, 'old_mergedLocalRoles'):
    utils.old_mergedLocalRoles = utils._mergedLocalRoles
utils.mergedLocalRoles = mergedLocalRoles
utils._mergedLocalRoles = mergedLocalRoles

def _allowedRolesAndUsers(ob):
    LOG('CPSCore utils', DEBUG, '_allowedRolesAndUsers()')
    aclu = ob.acl_users
    if hasattr(aclu, '_allowedRolesAndUsers'):
        return aclu._allowedRolesAndUsers(ob)
    # The userfolder does not have CPS group support
    allowed = {}
    for r in rolesForPermissionOn('View', ob):
        allowed[r] = 1
    localroles = utils.mergedLocalRoles(ob) # groups
    for user_or_group, roles in localroles.items():
        for role in roles:
            if allowed.has_key(role):
                allowed[user_or_group] = 1
    if allowed.has_key('Owner'):
        del allowed['Owner']
    return list(allowed.keys())

def allowedRolesAndUsers(self):
    """
    Return a list of roles, users and groups with View permission.
    Used by PortalCatalog to filter out items you're not allowed to see.
    """
    LOG('CPSCore utils', DEBUG, 'allowedRolesAndUsers()')
    ob = self._IndexableObjectWrapper__ob # Eeek, manual name mangling
    return _allowedRolesAndUsers(ob)
IndexableObjectWrapper.allowedRolesAndUsers = allowedRolesAndUsers

def _getAllowedRolesAndUsers(user):
    """Returns a list with all roles this user has + the username"""
    LOG('CPSCore utils', DEBUG, '_getAllowedRolesAndUsers()')
    # The userfolder does not have CPS group support
    result = list(user.getRoles())
    result.append('Anonymous')
    result.append('user:%s' % user.getUserName())
    # deal with groups
    getGroups = getattr(user, 'getGroups', None)
    if getGroups is not None:
        groups = tuple(user.getGroups()) + ('role:Anonymous',)
        if 'Authenticated' in result:
            groups = groups + ('role:Authenticated',)
        for group in groups:
            result.append('group:%s' % group)
    # end groups
    return result

def _listAllowedRolesAndUsers(self, user):
    LOG('CPSCore utils', DEBUG, '_listAllowedRolesAndUsers()')
    aclu = self.acl_users
    if hasattr(aclu, '_getAllowedRolesAndUsers'):
        return aclu._getAllowedRolesAndUsers(user)
    return CatalogTool.old_listAllowedRolesAndUsers(self, user)

if not hasattr(CatalogTool, 'old_listAllowedRolesAndUsers'):
    CatalogTool.old_getAllowedRolesAndUsers = CatalogTool._listAllowedRolesAndUsers

CatalogTool._listAllowedRolesAndUsers = _listAllowedRolesAndUsers

# Local role patching ends here

#
# Monkey patching ends here
#

from Products.CMFCore import utils as cmfutils
from Products.CMFCore.CMFCorePermissions import AddPortalContent, ManagePortal

# Don't remove.
import AllowModules

import ElementsTool
import EventServiceTool
import EventServicePatches
import TypesToolPatches
#import LoggerTool
#import MirrorTool
import ProxyTool
import ObjectRepositoryTool
import CPSWorkflowTool
import TreesTool
import CPSMembershipTool

from CPSWorkflowConfiguration import CPSWorkflowConfiguration
from CPSWorkflowConfiguration import addCPSWorkflowConfiguration

import ProxyBase

# register CPSWorkflow
import CPSWorkflow


tools = (
    EventServiceTool.EventServiceTool,
#    LoggerTool.LoggerTool,
#    MirrorTool.MirrorTool,
    ElementsTool.ElementsTool,
    ProxyTool.ProxyTool,
    ObjectRepositoryTool.ObjectRepositoryTool,
    CPSWorkflowTool.CPSWorkflowTool,
    TreesTool.TreesTool,
    CPSMembershipTool.CPSMembershipTool
)

contentClasses = (ProxyBase.ProxyFolder,
                  ProxyBase.ProxyDocument,
                  ProxyBase.ProxyFolderishDocument,
                  )

contentConstructors = (ProxyBase.addProxyFolder,
                       ProxyBase.addProxyDocument,
                       ProxyBase.addProxyFolderishDocument,
                       CPSMembershipTool.addCPSMembershipTool
                       )

fti = (ProxyBase.factory_type_information +
       ())

def initialize(registrar):
    cmfutils.ToolInit(
        'CPS Tools',
        tools = tools,
        product_name = 'CPSCore',
        icon = 'tool.gif',
    ).initialize(registrar)

    # Elements
    registrar.registerClass(
        ElementsTool.DefaultElement,
        permission='Add a Default Element',
        constructors=(
            ElementsTool.ElementsTool.manage_addDefaultElement,
        )
    )

    # Event Service
    registrar.registerClass(
        EventServiceTool.SubscriberDef,
        permission='Add a Subscriber Definition',
        constructors=(
            EventServiceTool.EventServiceTool.manage_addSubscriber,
        )
    )

    # Workflow Configuration Object
    registrar.registerClass(
        CPSWorkflowConfiguration,
        permission=ManagePortal,
        constructors=(addCPSWorkflowConfiguration,)
    )

    # Tree Cache
    registrar.registerClass(
        TreesTool.TreeCache,
        permission=ManagePortal,
        constructors=(TreesTool.TreesTool.manage_addCPSTreeCache,)
    )
    cmfutils.registerIcon(TreesTool.TreeCache, 'zmi/tree_icon.gif', globals())

    
    # CPS Content and Folder objects
    cmfutils.ContentInit(
        'CPS Default Documents',
        content_types = contentClasses,
        permission = AddPortalContent,
        extra_constructors = contentConstructors,
        fti = fti,
        ).initialize(registrar)
