# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
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

from zLOG import LOG, TRACE
from Acquisition import aq_base
from DateTime.DateTime import DateTime
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.CMFCore.utils import _checkPermission

from Products.PluginIndexes.TopicIndex.TopicIndex import TopicIndex
from Products.ZCatalog.ZCatalog import ZCatalog
from Products.CMFCore.CatalogTool import CatalogTool
from Products.CMFCore.CatalogTool import IndexableObjectWrapper
from Products.CMFCore.CMFCorePermissions import AccessInactivePortalContent

from Products.CPSCore.utils import getAllowedRolesAndUsersOfObject
from Products.CPSCore.utils import getAllowedRolesAndUsersOfUser

#
# Patch CatalogTool for generic allowedRolesAndUsers,
# and others catalog-related patches.
#

LOG('CPSCore', TRACE, 'Patching CatalogTool')


def cat_listAllowedRolesAndUsers(self, user):
    return getAllowedRolesAndUsersOfUser(user)

CatalogTool._listAllowedRolesAndUsers = cat_listAllowedRolesAndUsers


def cat_searchResults(self, REQUEST=None, **kw):
    """Calls ZCatalog.searchResults

    Adds extra arguments that limit the results to what the user is
    allowed to see.

    Takes care to allow users to further restrict the 'effective' range.
    """
    user = _getAuthenticatedUser(self)
    kw[ 'allowedRolesAndUsers' ] = self._listAllowedRolesAndUsers( user )

    if not _checkPermission( AccessInactivePortalContent, self ):
        base = aq_base( self )
        now = DateTime()
        usage = kw.get('effective_usage', 'range:min')
        eff = kw.get('effective', '')
        if hasattr( base, 'addIndex' ):   # Zope 2.4 and above
            if eff:
                eff = DateTime(eff)
                if usage == 'range:max':
                    kw[ 'effective' ] = { 'query' : min(eff, now), 'range' : 'max' }
                else:
                    kw[ 'effective' ] = { 'query' : (eff, now), 'range' : 'min:max' }
            else:
                kw[ 'effective' ] = { 'query' : now, 'range' : 'max' }
            kw[ 'expires' ] = { 'query' : now, 'range' : 'min' }
        else:                          # Zope 2.3
            if eff:
                if usage == 'range:max':
                    kw[ 'effective' ] = min(eff, now)
                    kw[ 'effective_usage'] = 'range:max'
                else:
                    kw[ 'effective' ] = (eff, now)
                    kw[ 'effective_usage' ] = 'range:min:max'
            else:
                kw[ 'effective' ] = now
                kw[ 'effective_usage'] = 'range:max'
            kw[ 'expires' ] = now
            kw[ 'expires_usage'  ] = 'range:min'
    return ZCatalog.searchResults(self, REQUEST, **kw)

CatalogTool.searchResults = cat_searchResults
CatalogTool.__call__ = cat_searchResults


def iow_allowedRolesAndUsers(self):
    """Return a list of roles, users and groups with View permission.

    Used by PortalCatalog to filter out items you're not allowed to see.
    """
    ob = self._IndexableObjectWrapper__ob
    return getAllowedRolesAndUsersOfObject(ob)

IndexableObjectWrapper.allowedRolesAndUsers = iow_allowedRolesAndUsers


def iow_localUsersWithRoles(self):
    """Return a list of users and groups having local roles.

    Used by PortalCatalog to find which objects have roles for given users
    and groups. Only return proxies: see how iow__getattr__ raises
    AttributeError when accessing this attribute.

    CPS-specific.
    """
    ob = self._IndexableObjectWrapper__ob
    local_roles = ['user:'+r[0] for r in ob.get_local_roles()]
    local_roles.extend(['group:'+r[0] for r in ob.get_local_group_roles()])
    return local_roles

IndexableObjectWrapper.localUsersWithRoles = iow_localUsersWithRoles


def iow__getattr__(self, name):
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

IndexableObjectWrapper.__getattr__ = iow__getattr__


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


LOG('CPSCore', TRACE, 'Patching TopicIndex')

def topicindex_clear(self):
    """Fixing CMF method that remove all filter."""
    for fid, filteredSet in self.filteredSets.items():
        filteredSet.clear()

TopicIndex.clear = topicindex_clear
