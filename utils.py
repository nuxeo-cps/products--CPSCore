# -*- coding: iso-8859-15 -*-
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

The only role-related functions that should be imported by external code
are:
  - mergedLocalRoles(object, withgroups=0)
  - mergedLocalRolesWithPath(object, withgroups=0)
  - getAllowedRolesAndUsersOfObject(object)
  - getAllowedRolesAndUsersOfUser(user)

Other utility functions:
  - _isinstance(ob, class)
  - makeId(s, lower=0)

This code uses if possible the following methods on the user folder:
  - mergedLocalRoles
  - mergedLocalRolesWithPath
  - getAllowedRolesAndUsersOfObject
  - getAllowedRolesAndUsersOfUser
"""

import string
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl.PermissionRole import rolesForPermissionOn
from Products import CMFCore
from DateTime.DateTime import DateTime
from random import randrange
from types import ListType
import re

#
# some shared constants
# see AllowedModules to check if they are public
KEYWORD_DOWNLOAD_FILE = 'downloadFile'
KEYWORD_ARCHIVED_REVISION = 'archivedRevision'
KEYWORD_SWITCH_LANGUAGE = 'switchLanguage'
KEYWORD_VIEW_LANGUAGE = 'viewLanguage'
KEYWORD_VIEW_ZIP = 'viewZip'
SESSION_LANGUAGE_KEY = 'CPS_SWITCH_LANGUAGE'
REQUEST_LANGUAGE_KEY = 'CPS_VIEW_LANGUAGE'


# Safe hasattr that doesn't catch unwanted exceptions and checks on base.
_marker = []
def bhasattr(ob, attr):
    return getattr(aq_base(ob), attr, _marker) is not _marker


#
# Main functions
#

def mergedLocalRoles(object, withgroups=0):
    """Return a merging of object and its ancestors' local roles

    When called with withgroups=1, the keys are
    of the form user:foo and group:bar.
    """
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and bhasattr(aclu, 'mergedLocalRoles'):
        return aclu.mergedLocalRoles(object, withgroups)
    # Default implementation:
    merged = {}
    object = getattr(object, 'aq_inner', object)
    while 1:
        if hasattr(object, '__ac_local_roles__'):
            dict = object.__ac_local_roles__ or {}
            if callable(dict): dict = dict()
            for k, v in dict.items():
                if withgroups:
                    k = 'user:'+k
                if merged.has_key(k):
                    merged[k] = merged[k] + v
                elif v:
                    merged[k] = v
        if hasattr(object, 'aq_parent'):
            object=object.aq_parent
            object=getattr(object, 'aq_inner', object)
            continue
        if hasattr(object, 'im_self'):
            object=object.im_self
            object=getattr(object, 'aq_inner', object)
            continue
        break
    return merged

def mergedLocalRolesWithPath(object, withgroups=0):
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and bhasattr(aclu, 'mergedLocalRolesWithPath'):
        return aclu.mergedLocalRolesWithPath(object, withgroups)
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
    """Get the roles and users that can View this object."""
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

def _isinstance(ob, cls):
    try:
        return isinstance(ob, cls)
    except TypeError:
        # In python 2.1 isinstance() raises TypeError
        # instead of returning 0 for ExtensionClasses.
        return 0

_translation_table = string.maketrans(
    # XXX candidates: @°+=`|
    r""""'/\:; &ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöøùúûüýÿ""",
    r"""--------AAAAAACEEEEIIIINOOOOOOUUUUYaaaaaaceeeeiiiinoooooouuuuyy""")

_ok_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_.'

# TODO: this assumes we're using latin-1
# TODO: similar code is duplicated in other places
# (./CPSDefault/skins/cps_default/computeId.py,
# ./CPSForum/skins/forum_default/forum_create.py, ./CPSSchemas/BasicWidgets.py,
# ./CPSWebMail/Attachment.py...)
def makeId(s, lower=0, portal_type=None):
    """Generate an id from a given string <s>.

    This method avoids collisions.
    """
    # Normalization
    id = s.translate(_translation_table)
    id = id.replace('Æ', 'AE')
    id = id.replace('æ', 'ae')
    id = id.replace('Œ', 'OE')
    id = id.replace('œ', 'oe')
    id = id.replace('ß', 'ss')
    id = ''.join([c for c in id if c in _ok_chars])
    if lower:
        id = id.lower()

    # Avoiding duplication of meaningless chars
    id = re.sub('-+', '-', id)
    id = re.sub('_+', '_', id)
    id = re.sub('\.+', '.', id)

    # Avoiding annoying presence of meaningless chars
    while id.startswith('-') or id.startswith('_') or id.startswith('.'):
        id = id[1:]
    while id.endswith('-') or id.endswith('_') or id.endswith('.'):
        id = id[:-1]

    # Fallback if empty
    if not id:
        newid = str(int(DateTime())) + str(randrange(1000, 10000))
        return newid
    return id

def isUserAgentMsie(request):
    """Return wether the user agent performing the request is
    an MSIE user agent"""
    user_agent = request.get('HTTP_USER_AGENT')
    if user_agent.find('MSIE') != -1:
        return 1
    else:
        return 0

def resetSessionLanguageSelection(request):
    """Clear documents language selection done by switchLanguage"""
    try:
        del request.SESSION[SESSION_LANGUAGE_KEY]
    except KeyError:
        pass

def manageCPSLanguage(context, action, default_language, languages):
    """Manage available a languages in a CPS portal with Localizer"""

    catalogs = context.Localizer.objectValues()
    catalogs.append(context.Localizer)
    portal = context.portal_url.getPortalObject()

    if not isinstance(languages, ListType):
        languages = [languages]

    if languages is None and action in ('add', 'delete'):
        psm = 'psm_language_error_select_at_least_one_item'

    elif action == 'add':
        # Make languages available in Localizer
        for lang in languages:
            for catalog in catalogs:
                catalog.manage_addLanguage(lang)

        # XXX needs a tools to register po files for domains
        # Update Localizer/default only !
        i18n_method = getattr(portal,'i18n Updater')
        i18n_method()
        psm = 'psm_language_added'

    elif action == 'delete':
        # Make unavailable languages in Localizer
        for catalog in catalogs:
            catalog.manage_delLanguages(languages)
        psm = 'psm_language_deleted'

    elif action == 'chooseDefault':
        for catalog in catalogs:
            catalog.manage_changeDefaultLang(default_language)
        psm = 'psm_default_language_set'

    else:
        psm = ''

    return psm
