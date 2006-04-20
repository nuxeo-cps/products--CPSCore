# -*- coding: iso-8859-15 -*-
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
"""Miscellaneous utility functions.

The only role-related functions that should be imported by external code
are:
  - mergedLocalRoles(obj, withgroups=0)
  - mergedLocalRolesWithPath(obj, withgroups=0)
  - getAllowedRolesAndUsersOfObject(obj)
  - getAllowedRolesAndUsersOfUser(user)

This code uses if possible the following methods on the user folder:
  - mergedLocalRoles
  - mergedLocalRolesWithPath
  - getAllowedRolesAndUsersOfObject
  - getAllowedRolesAndUsersOfUser
"""

from copy import deepcopy

from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl.PermissionRole import rolesForPermissionOn
from Products import CMFCore
from warnings import warn
from Products.CPSUtil.id import generateId

# some shared constants
# see AllowedModules to check if they are public
KEYWORD_DOWNLOAD_FILE = 'downloadFile'
KEYWORD_ARCHIVED_REVISION = 'archivedRevision'
KEYWORD_SWITCH_LANGUAGE = 'switchLanguage'
KEYWORD_VIEW_LANGUAGE = 'viewLanguage'
KEYWORD_VIEW_ZIP = 'viewZip'
SESSION_LANGUAGE_KEY = 'CPS_SWITCH_LANGUAGE'
REQUEST_LANGUAGE_KEY = 'CPS_VIEW_LANGUAGE'
ALL_LOCALES = ['ae', 'am', 'ar', 'at', 'az', 'be', 'bg', 'bh', 'br',
               'by', 'ca', 'ch', 'cu', 'cz', 'de', 'dj', 'dk', 'dz',
               'ee', 'eg', 'en', 'es', 'eu', 'fi', 'fr', 'ge', 'gr',
               'hr', 'hu', 'il', 'iq', 'is', 'it', 'jo', 'jp', 'km',
               'kw', 'la', 'lb', 'lt', 'ly', 'ma', 'mg', 'mk', 'mx',
               'nl', 'no', 'om', 'pl', 'ps', 'pt', 'pt_BR', 'qa', 'qc',
               'ro', 'ru', 'sa', 'si', 'sk', 'so', 'su', 'sv', 'sy',
               'th', 'tn', 'tr', 'ua', 'uk', 'un', 'us', 'uy', 'vn',
               'ye', 'yu']


# Safe hasattr that doesn't catch unwanted exceptions and checks on base.
_marker = []
def bhasattr(ob, attr):
    return getattr(aq_base(ob), attr, _marker) is not _marker


#
# Main functions
#

def mergedLocalRoles(obj, withgroups=0):
    """Return a merging of obj and its ancestors' local roles

    When called with withgroups=1, the keys are
    of the form user:foo and group:bar.
    """
    aclu = getattr(obj, 'acl_users', None)
    if aclu is not None and bhasattr(aclu, 'mergedLocalRoles'):
        return aclu.mergedLocalRoles(obj, withgroups)
    # Default implementation:
    merged = {}
    obj = getattr(obj, 'aq_inner', obj)
    while 1:
        if hasattr(obj, '__ac_local_roles__'):
            d = obj.__ac_local_roles__ or {}
            if callable(d):
                d = d()
            for k, v in d.items():
                if withgroups:
                    k = 'user:' + k
                if merged.has_key(k):
                    merged[k] = merged[k] + v
                elif v:
                    merged[k] = v
        if hasattr(obj, 'aq_parent'):
            obj = obj.aq_parent
            obj = getattr(obj, 'aq_inner', obj)
            continue
        if hasattr(obj, 'im_self'):
            obj = obj.im_self
            obj = getattr(obj, 'aq_inner', obj)
            continue
        break
    return deepcopy(merged)

def mergedLocalRolesWithPath(obj, withgroups=0):
    aclu = getattr(obj, 'acl_users', None)
    if aclu is not None and bhasattr(aclu, 'mergedLocalRolesWithPath'):
        return aclu.mergedLocalRolesWithPath(obj, withgroups)
    # Default implementation:
    return {}

def getAllowedRolesAndUsersOfUser(user):
    """Return the roles and groups a user has."""
    aclu = aq_parent(aq_inner(user))
    # XXX Should really call a method on the user itself
    if hasattr(aclu, 'getAllowedRolesAndUsersOfUser'):
        return aclu.getAllowedRolesAndUsersOfUser(user)
    if hasattr(aclu, '_getAllowedRolesAndUsers'): # old spelling
        return aclu._getAllowedRolesAndUsers(user)
    # Default implementation:
    result = list(user.getRoles())
    if 'Anonymous' not in result:
        result.append('Anonymous')
    result.append('user:' + user.getUserName())
    if hasattr(aq_base(user), 'getComputedGroups'):
        groups = user.getComputedGroups()
    elif hasattr(aq_base(user), 'getGroups'):
        groups = user.getGroups() + ('role:Anonymous',)
        if 'Authenticated' in result:
            groups = groups + ('role:Authenticated',)
    else:
        groups = ('role:Anonymous',)
    for group in groups:
        result.append('group:' + group)
    return result

def getAllowedRolesAndUsersOfObject(ob):
    """Get the roles and users that can View this obj."""
    aclu = getattr(ob, 'acl_users', None)
    if bhasattr(aclu, 'getAllowedRolesAndUsersOfObject'):
        return aclu.getAllowedRolesAndUsersOfObject(ob)
    if bhasattr(aclu, '_allowedRolesAndUsers'): # old spelling
        return aclu._allowedRolesAndUsers(ob)
    # Default implementation:
    allowed = {}
    for r in rolesForPermissionOn('View', ob):
        allowed[r] = None
    localroles = mergedLocalRoles(ob, withgroups=1)
    for user_or_group, roles in localroles.items():
        for role in roles:
            if allowed.has_key(role):
                allowed[user_or_group] = None
    if allowed.has_key('Owner'):
        del allowed['Owner']
    return allowed.keys()

#
# Patch CMFCore.utils for generic mergedLocalRoles
#

CMFCore.utils.mergedLocalRoles = mergedLocalRoles
CMFCore.utils._mergedLocalRoles = mergedLocalRoles

#
# Utility functions
#

# XXX this is deprecated and will be removed.
def _isinstance(ob, cls):
    try:
        return isinstance(ob, cls)
    except TypeError:
        # In python 2.1 isinstance() raises TypeError
        # instead of returning 0 for ExtensionClasses.
        return 0

# Note: this code must be kept in sync with ProxyTool.getBestRevision
def resetSessionLanguageSelection(REQUEST):
    """Clear documents language selection done by switchLanguage"""
    if getattr(REQUEST, 'SESSION', None) is not None:
        if REQUEST.SESSION.has_key(SESSION_LANGUAGE_KEY):
            del REQUEST.SESSION[SESSION_LANGUAGE_KEY]

def resetRequestLanguageSelection(REQUEST):
    """Clear documents language selection done by viewLanguage"""
    if getattr(REQUEST, 'other', None) is not None:
        if REQUEST_LANGUAGE_KEY in REQUEST.other:
            del REQUEST.other[REQUEST_LANGUAGE_KEY]

def makeId(s, max_chars=80, lower=0, portal_type=None):
    warn("The method, "
         "'Products.CPSCore.utils.makeId' "
         "is a deprecated compatiblity alias for "
         "'Products.CPSUtil.id.generateId'; "
         "please use the new method instead.",
         DeprecationWarning)
    return generateId(s, max_chars=max_chars, lower=lower,
                      portal_type=portal_type)
