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
"""Miscellaneous utility functions.
"""

from zLOG import LOG, INFO, DEBUG
import string

# Local role (group) support monkey patches start here

from AccessControl.PermissionRole import rolesForPermissionOn
from Products.CMFCore import utils
from Products.CMFCore.CatalogTool import IndexableObjectWrapper, \
     CatalogTool

LOG('CPSCore.utils', INFO, 'Patching CMF local role support')

def mergedLocalRoles(object, withgroups=0):
    #LOG('CPSCore utils', DEBUG, 'mergedLocalRoles()')
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and hasattr(aclu, 'mergedLocalRoles'):
        return aclu.mergedLocalRoles(object, withgroups)
    return utils.old_mergedLocalRoles(object)

def mergedLocalRolesWithPath(object, withgroups=0):
    #LOG('CPSCore utils', DEBUG, 'mergedLocalRolesWithPath()')
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and hasattr(aclu, 'mergedLocalRolesWithPath'):
        return aclu.mergedLocalRolesWithPath(object, withgroups)
    else:
        return {}

if not hasattr(utils, 'old_mergedLocalRoles'):
    utils.old_mergedLocalRoles = utils._mergedLocalRoles
utils.mergedLocalRoles = mergedLocalRoles
utils._mergedLocalRoles = mergedLocalRoles
utils.mergedLocalRolesWithPath = mergedLocalRolesWithPath

def _allowedRolesAndUsers(ob):
    #LOG('CPSCore utils', DEBUG, '_allowedRolesAndUsers()')

    aclu = getattr(ob, 'acl_users', None)
    if aclu is not None and hasattr(aclu, '_allowedRolesAndUsers'):
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
    #LOG('CPSCore utils', DEBUG, '_getAllowedRolesAndUsers()')

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
    #LOG('CPSCore utils', DEBUG, '_listAllowedRolesAndUsers()')
    aclu = self.acl_users
    if hasattr(aclu, '_getAllowedRolesAndUsers'):
        return aclu._getAllowedRolesAndUsers(user)
    return CatalogTool.old_listAllowedRolesAndUsers(self, user)

if not hasattr(CatalogTool, 'old_listAllowedRolesAndUsers'):
    CatalogTool.old_listAllowedRolesAndUsers = \
        CatalogTool._listAllowedRolesAndUsers

CatalogTool._listAllowedRolesAndUsers = _listAllowedRolesAndUsers

# Local role monkey patching ends here

def _isinstance(ob, cls):
    try:
        return isinstance(ob, cls)
    except TypeError:
        # In python 2.1 isinstance() raises TypeError
        # instead of returning 0 for ExtensionClasses.
        return 0

_translation_table = string.maketrans(
    r"'\;/ &:¿¡¬√ƒ≈«»… ÀÃÕŒœ—“”‘’÷ÿŸ⁄€‹›‡·‚„‰ÂÁËÈÍÎÏÌÓÔÒÚÛÙıˆ¯˘˙˚¸˝ˇ",
    r"_______AAAAAACEEEEIIIINOOOOOOUUUUYaaaaaaceeeeiiiinoooooouuuuyy")

# XXX: this assumes we're using latin-1
def makeId(s, lower=0):
    "Make id from string"
    s = s.replace('∆', 'AE')
    s = s.replace('Ê', 'ae')
    id = s.translate(_translation_table)
    if lower:
        id = id.lower()
    return id
