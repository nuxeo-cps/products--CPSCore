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
  - getAllowedRolesAndUsersOfUser(user)
  - getAllowedRolesAndUsersOfObject(object)

Other utility functions:
  - _isinstance(ob, class)
  - makeId(s, lower=0)

"""

from zLOG import LOG, DEBUG, TRACE
import string

# Local role (group) support monkey patches start here

from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl.PermissionRole import rolesForPermissionOn
from Products.CMFCore import utils
from Products.CMFCore.CatalogTool import IndexableObjectWrapper, \
     CatalogTool
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl
from DateTime.DateTime import DateTime
from Products.PluginIndexes.TopicIndex.TopicIndex import TopicIndex
from random import randrange

LOG('CPSCore.utils', TRACE, 'Patching CMF local role support')

def mergedLocalRoles(object, withgroups=0):
    #LOG('CPSCore utils', DEBUG, 'mergedLocalRoles()')
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and hasattr(aclu, 'mergedLocalRoles'):
        return aclu.mergedLocalRoles(object, withgroups)
    # XXX should code old implementation directly here
    return utils.old_mergedLocalRoles(object)

def mergedLocalRolesWithPath(object, withgroups=0):
    #LOG('CPSCore utils', DEBUG, 'mergedLocalRolesWithPath()')
    aclu = getattr(object, 'acl_users', None)
    if aclu is not None and hasattr(aclu, 'mergedLocalRolesWithPath'):
        return aclu.mergedLocalRolesWithPath(object, withgroups)
    # Default implementation:
    return {}

if not hasattr(utils, 'old_mergedLocalRoles'):
    utils.old_mergedLocalRoles = utils._mergedLocalRoles
utils.mergedLocalRoles = mergedLocalRoles
utils._mergedLocalRoles = mergedLocalRoles
utils.mergedLocalRolesWithPath = mergedLocalRolesWithPath

def getAllowedRolesAndUsersOfObject(ob):
    """Get the roles and users that can View this object."""
    aclu = getattr(ob, 'acl_users', None)
    if hasattr(aclu, '_allowedRolesAndUsers'):
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

# XXX should be calling above function.
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

# XXX should be renamed to avoid confusion
def allowedRolesAndUsers(self):
    """
    Return a list of roles, users and groups with View permission.
    Used by PortalCatalog to filter out items you're not allowed to see.
    """
    #LOG('CPSCore utils', DEBUG, 'allowedRolesAndUsers()')
    ob = self._IndexableObjectWrapper__ob # Eeek, manual name mangling
    return _allowedRolesAndUsers(ob)

IndexableObjectWrapper.allowedRolesAndUsers = allowedRolesAndUsers


LOG('CPSCore.utils', DEBUG,
    'Adding localUsersWithRoles to IndexableObjectWrapper')
def localUsersWithRoles(self):
    """
    Return a list of users and groups having local roles.

    Used by PortalCatalog to find which objects have roles for given users and
    groups. Only return proxies: see how __cps_wrapper_getattr__ raises
    AttributeError when accessing this attribute.
    """
    ob = self._IndexableObjectWrapper__ob
    # XXX herve: correct me if I'm wrong but repository documents' roles already
    # are some "merge" of proxies' roles; so this index doesn't seem relevant
    # since it's like a copy of the allowedRolesAndUsers index.
    local_roles = ['user:%s' % r[0] for r in ob.get_local_roles()]
    local_roles.extend(['group:%s' % r[0] for r in ob.get_local_group_roles()])
    return local_roles

IndexableObjectWrapper.localUsersWithRoles = localUsersWithRoles


def getAllowedRolesAndUsersOfUser(user):
    """Return the roles and groups this user has."""
    aclu = aq_parent(aq_inner(user))
    if hasattr(aclu, '_getAllowedRolesAndUsers'):
        return aclu._getAllowedRolesAndUsers(user)
    # Default implementation:
    result = list(user.getRoles())
    if 'Anonymous' not in result:
        result.append('Anonymous')
    result.append('user:%s' % user.getUserName())
    if hasattr(aq_base(user), 'getComputedGroups'):
        groups = user.getComputedGroups()
    elif hasattr(aq_base(user), 'getGroups'):
        groups = user.getGroups() + ('role:Anonymous',)
        if 'Authenticated' in result:
            groups = groups + ('role:Authenticated',)
    else:
        groups = ('role:Anonymous',)
    for group in groups:
        result.append('group:%s' % group)
    return result

# XXX should be calling getAllowedRolesAndUsersOfUser
# XXX should be removed from API, instead use above function
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

# XXX should be calling getAllowedRolesAndUsersOfUser
# XXX should be renamed to avoid confusion
def _listAllowedRolesAndUsers(self, user):
    return _getAllowedRolesAndUsers(user)
CatalogTool._listAllowedRolesAndUsers = _listAllowedRolesAndUsers


LOG('CPSCore.utils', TRACE, 'Patching CMF Catalog IndexableObjectWrapper')
def __cps_wrapper_getattr__(self, name):
    """This is the indexable wrapper getter for CPS,
    proxy try to get the repository document attributes,
    document in the repository hide some attributes to save some space."""
    vars = self._IndexableObjectWrapper__vars
    if vars.has_key(name):
        return vars[name]
    ob = self._IndexableObjectWrapper__ob
    proxy = None
    # XXX TODO: use _isinstance(ProxyBase) need to fix import mess
    if hasattr(ob, '_docid') and name not in (
            'getId', 'id', 'path', 'getPhysicalPath', 'splitPath', 'modified',
            'uid', 'container_path', 'Languages'):
        proxy = ob
        ob = ob.getContent()
        ## The following seems problematic with Zope 2.7.1 and higher
        ## I haven't been able to know if it was related to TextIndexNG2
        ## or not (see comments below). I think it is not, and might be related
        ## to recent Zope's more tight security checks resulting in None objects
        ## being returned sometimes. A post on zope-dev has explained this a bit,
        ## but no definitive explanation has yet been given.
        ## This seems harmless in most cases, as it has not been changed in 2.7.2.
        ## Main problems have been reported by CNCC : leaving these two lines
        ## make their main installer unusable : it fails installing a site
        ## by crashing on an AttributeError. Commenting the lines have been
        ## a temporary workaround which seems to work.
        #if ob is None:
        #    raise AttributeError
    elif 'portal_repository' in ob.getPhysicalPath():
        if name in ('SearchableText', 'Title'):
            raise AttributeError
    try:
        ## This try/except have been added to make Unilog's projects work
        ## fine with TextIndexNG2
        ## This index tries to acces directly to meta_type attribute at
        ## object creation, and in CPSDocuments, a first indexation takes
        ## place before the real object is created
        ## returning None in this specific case is ok because the object
        ## will always be reindexed correctly later on (according to fg).
        ret = getattr(ob, name)
    except AttributeError:
        if name == 'meta_type':
            return None
        ## In all other cases, we reraise the exception to let the potential
        ## problems be visible outside of this code.
        raise
    if proxy is not None:
        if name == 'SearchableText':
            ret = ret() + ' ' + proxy.getId()  # so we can search on id
    return ret
IndexableObjectWrapper.__getattr__ = __cps_wrapper_getattr__

def container_path(self):
    """This is used to produce an index
    return the parent full path."""
    ob = self._IndexableObjectWrapper__ob
    return '/'.join(ob.getPhysicalPath()[:-1])

IndexableObjectWrapper.container_path = container_path

def relative_path(self):
    """This is used to produce a metadata
    return a path relative to the portal."""
    ob = self._IndexableObjectWrapper__ob
    try:
        return ob.portal_url.getRelativeContentURL(ob)
    except AttributeError:
        # broken object can't aquire portal_url
        return ''
IndexableObjectWrapper.relative_path = relative_path

def relative_path_depth(self):
    """This is used to produce an index
    return the path depth relative to the portal."""
    ob = self._IndexableObjectWrapper__ob
    try:
        return len(ob.portal_url.getRelativeContentPath(ob))
    except AttributeError:
        # broken object can't aquire portal_url
        return -1
IndexableObjectWrapper.relative_path_depth = relative_path_depth


LOG('CPSCore.utils', TRACE, 'Patching Zope TopicIndex.clear method')
def topicindex_clear(self):
    """Fixing cmf method that remove all filter."""
    for fid, filteredSet in self.filteredSets.items():
        filteredSet.clear()
TopicIndex.clear = topicindex_clear


LOG('CPSCore.utils', TRACE, 'Patching CMF DublinCore never expires date')
# this remove the overflow pb when using a DateIndex for expires
DefaultDublinCoreImpl._DefaultDublinCoreImpl__CEILING_DATE = DateTime(3000, 0)

# Local role monkey patching ends here


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
    r"""________AAAAAACEEEEIIIINOOOOOOUUUUYaaaaaaceeeeiiiinoooooouuuuyy""")

_ok_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_.'

# XXX: this assumes we're using latin-1
def makeId(s, lower=0):
    "Make id from string"
    id = s.translate(_translation_table)
    id = id.replace('Æ', 'AE')
    id = id.replace('æ', 'ae')
    id = id.replace('Œ', 'OE')
    id = id.replace('œ', 'oe')
    id = id.replace('ß', 'ss')
    id = ''.join([c for c in id if c in _ok_chars])
    while id.startswith('_') or id.startswith('.'):
        id = id[1:]
    while id.endswith('_'):
        id = id[:-1]
    if not id:
        # Fallback if empty or incorrect
        newid = str(int(DateTime())) + str(randrange(1000, 10000))
        return newid
    if lower:
        id = id.lower()
    return id

def isUserAgentMsie(request):
    """Return wether the user agent performing the request is
    an MSIE user agent"""
    user_agent = request.get('HTTP_USER_AGENT')
    if user_agent.find('MSIE') != -1:
        return True
    else:
        return False
