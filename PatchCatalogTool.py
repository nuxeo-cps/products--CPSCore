# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
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
"""Patch CMF CatalogTool
"""
from zLOG import LOG, DEBUG, INFO
from types import TupleType, ListType
from Acquisition import aq_base
from DateTime.DateTime import DateTime
from Products.ZCatalog.ZCatalog import ZCatalog
from Products.CMFCore.interfaces.portal_catalog import \
     IndexableObjectWrapper as IIndexableObjectWrapper
from Products.CMFCore.CatalogTool import CatalogTool
from Products.CMFCore.utils import getToolByName, _getAuthenticatedUser, \
     _checkPermission
from Products.CMFCore.CMFCorePermissions import AccessInactivePortalContent

from Products.CPSCore.utils import getAllowedRolesAndUsersOfObject, \
     getAllowedRolesAndUsersOfUser, _isinstance
from Products.CPSCore.ProxyBase import ProxyBase, KEYWORD_SWITCH_LANGUAGE, \
     KEYWORD_VIEW_LANGUAGE, SESSION_LANGUAGE_KEY
from Products.PluginIndexes.TopicIndex.TopicIndex import TopicIndex


class IndexableObjectWrapper:
    """This is a CPS adaptation of
    CMFCore.CatalogTool.IndexableObjectWrapper"""
    __implements__ = IIndexableObjectWrapper

    def __init__(self, vars, ob, lang=None, is_default_proxy=0):
        self.__vars = vars
        self.__ob = ob
        self.__lang = lang
        self.__is_default_proxy = is_default_proxy

    def __getattr__(self, name):
        """This is the indexable wrapper getter for CPS,
        proxy try to get the repository document attributes,
        document in the repository hide some attributes to save some space."""
        vars = self.__vars
        if vars.has_key(name):
            return vars[name]
        ob = self.__ob
        proxy = None
        if _isinstance(ob, ProxyBase):
            proxy = ob
            if (self.__is_default_proxy and
                name in ('getL10nTitles', 'getL10nDescriptions')) or (
                name in ('getId', 'id', 'path', 'uid', 'modified',
                         'getPhysicalPath', 'splitPath', 'getProxyLanguages')):
                # we use the proxy
                pass
            else:
                # use the repository document instead of the proxy
                ob = ob.getContent(lang=self.__lang)
        elif 'portal_repository' in ob.getPhysicalPath():
            if name in ('SearchableText', 'Title'):
                # skip useless indexes for repository document
                raise AttributeError

        try:
            ret = getattr(ob, name)
        except AttributeError:
            if name == 'meta_type':
                # this is a fix for TextIndexNG2
                return None
            raise

        if proxy is not None and name == 'SearchableText':
            # we add proxy id to searchableText
            ret = ret() + ' ' + proxy.getId()

        return ret

    def allowedRolesAndUsers(self):
        """
        Return a list of roles, users and groups with View permission.
        Used by PortalCatalog to filter out items you're not allowed to see.
        """
        return getAllowedRolesAndUsersOfObject(self.__ob)

    def localUsersWithRoles(self):
        """
        Return a list of users and groups having local roles.
        Used by PortalCatalog to find which objects have roles for given
        users and groups.
        Only return proxies: see above __getattr__ raises
        AttributeError when accessing this attribute.
        """
        ob = self.__ob
        local_roles = ['user:%s' % r[0] for r in ob.get_local_roles()]
        local_roles.extend(
            ['group:%s' % r[0] for r in ob.get_local_group_roles()])
        return local_roles

    def container_path(self):
        """This is used to produce an index
        return the parent full path."""
        return '/'.join(self.__ob.getPhysicalPath()[:-1])

    def relative_path(self):
        """This is used to produce a metadata
        return a path relative to the portal."""
        utool = getToolByName(self, 'portal_url', None)
        ret = ''
        if utool:
            # broken object can't aquire portal_url
            ret = utool.getRelativeContentURL(self.__ob)
        return ret

    def relative_path_depth(self):
        """This is used to produce an index
        return the path depth relative to the portal."""
        rpath = self.relative_path()
        ret = -1
        if rpath:
            ret = rpath.count('/')+1
        return ret


### Patching CatalogTool methods
def cat_catalog_object(self, object, uid, idxs=[], update_metadata=1):
    """Wraps the object with workflow and accessibility
    information just before cataloging."""
    LOG('CatalogToolPatch.catalog_object', DEBUG, 'index uid %s  obj %s' % (
        uid, object))
    wf = getattr(self, 'portal_workflow', None)
    if wf is not None:
        vars = wf.getCatalogVariablesFor(object)
    else:
        vars = {}
    path = uid.split('/')
    proxy = None
    if _isinstance(object, ProxyBase):
        proxy = object
        languages = proxy.getProxyLanguages()
    if proxy is None or len(languages) == 1 or \
           KEYWORD_VIEW_LANGUAGE in path:
        w = IndexableObjectWrapper(vars, object)
        ZCatalog.catalog_object(self, w, uid, idxs, update_metadata)
    else:
        if len(languages) == 2:
            # remove previous entry with uid path
            self.uncatalog_object(uid)
        # we index all available translation of the proxy
        # with uid/viewLanguage/language for path
        default_language = proxy.getDefaultLanguage()
        default_uid = uid
        for language in languages:
            is_default_proxy = 0
            if language == default_language:
                is_default_proxy = 1
            uid = default_uid + '/%s/%s' % (KEYWORD_VIEW_LANGUAGE,
                                            language)
            w = IndexableObjectWrapper(vars, proxy, language,
                                       is_default_proxy=is_default_proxy)
            LOG('CatalogToolPatch.catalog_object', DEBUG,
                'index uid locale %s' % uid)
            ZCatalog.catalog_object(self, w, uid, idxs, update_metadata)

CatalogTool.catalog_object = cat_catalog_object
LOG('CatalogToolPatch', INFO, 'Patching CMF CatalogTool.catalog_object')


def cat_unindexObject(self, object):
    """Remove from catalog."""
    default_uid = self._CatalogTool__url(object)
    proxy = None
    if _isinstance(object, ProxyBase):
        proxy = object
        languages = proxy.getProxyLanguages()
    if proxy is None or len(languages) == 1:
        self.uncatalog_object(default_uid)
    else:
        for language in languages:
            # remove all translation of the proxy
            uid = default_uid + '/%s/%s' % (KEYWORD_VIEW_LANGUAGE,
                                            language)
            self.uncatalog_object(uid)

CatalogTool.unindexObject = cat_unindexObject
LOG('CatalogToolPatch', INFO, 'Patching CMF CatalogTool.unindexObject')


def cat_listAllowedRolesAndUsers(self, user):
    """Returns a list with all roles this user has + the username"""
    return getAllowedRolesAndUsersOfUser(user)

CatalogTool._listAllowedRolesAndUsers = cat_listAllowedRolesAndUsers
LOG('CatalogToolPatch', INFO,
    'Patching CMF CatalogTool._listAllowedRolesAndUsers')


def cat_convertQuery(self, kw):
    # Convert query to modern syntax
    for k in 'effective', 'expires':
        kusage = k+'_usage'
        if not kw.has_key(kusage):
            continue
        usage = kw[kusage]
        if not usage.startswith('range:'):
            raise ValueError("Incorrect usage %s" % `usage`)
        kw[k] = {'query': kw[k], 'range': usage[6:]}
        del kw[kusage]
CatalogTool._convertQuery = cat_convertQuery

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

        self._convertQuery(kw)

        # Intersect query restrictions with those implicit to the tool
        for k in 'effective', 'expires':
            if kw.has_key(k):
                range = kw[k]['range'] or ''
                query = kw[k]['query']
                if (not isinstance(query, TupleType) and
                    not isinstance(query, ListType)):
                    query = (query,)
            else:
                range = ''
                query = None
            if range.find('min') > -1:
                lo = min(query)
            else:
                lo = None
            if range.find('max') > -1:
                hi = max(query)
            else:
                hi = None
            if k == 'effective':
                if hi is None or hi > now:
                    hi = now
                if lo is not None and hi < lo:
                    return ()
            else: # 'expires':
                if lo is None or lo < now:
                    lo = now
                if hi is not None and hi < lo:
                    return ()
            # Rebuild a query
            if lo is None:
                query = hi
                range = 'max'
            elif hi is None:
                query = lo
                range = 'min'
            else:
                query = (lo, hi)
                range = 'min:max'
            kw[k] = {'query': query, 'range': range}

    return ZCatalog.searchResults(self, REQUEST, **kw)

CatalogTool.searchResults = cat_searchResults
CatalogTool.__call__ = cat_searchResults
LOG('CatalogToolPatch', INFO,
    'Patching CMF CatalogTool.searchResults and __call__')


### TopicIndex.clear patch
def topicindex_clear(self):
    """Fixing cmf method that remove all filter."""
    for fid, filteredSet in self.filteredSets.items():
        filteredSet.clear()
TopicIndex.clear = topicindex_clear
LOG('CatalogToolPatch', INFO, 'Patching Zope TopicIndex.clear method')



