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
from ZODB.loglevels import TRACE
from logging import getLogger

from Acquisition import aq_base, aq_parent, aq_inner
from Products.ZCatalog.ZCatalog import ZCatalog
from Products.CMFCore.interfaces.portal_catalog import \
     IndexableObjectWrapper as IIndexableObjectWrapper
from Products.CMFCore.CatalogTool import CatalogTool
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware
from Products.CMFCore.utils import getToolByName
from Products.CPSCore.utils import getAllowedRolesAndUsersOfObject, \
     getAllowedRolesAndUsersOfUser
from Products.CPSCore.utils import KEYWORD_VIEW_LANGUAGE, ALL_LOCALES
from Products.CPSCore.ProxyBase import ProxyBase

logger = getLogger('CPSCore.PatchCMFCoreCatalogTool')

# We're monkey patching CMFCatalogAware here because it's
# really related to cataloging

if 'localUsersWithRoles' not in CMFCatalogAware._cmf_security_indexes:
    CMFCatalogAware._cmf_security_indexes += ('localUsersWithRoles',)


class IndexableObjectWrapper:
    """This is a CPS adaptation of
    CMFCore.CatalogTool.IndexableObjectWrapper"""
    __implements__ = IIndexableObjectWrapper

    _cps_patch_logger = getLogger(
        'CPSCore.PatchCMFCoreCatalogTool.IndexableObjectWrapper')

    def __init__(self, vars, ob, lang=None, uid=None):
        self.__vars = vars
        self.__ob = ob
        self.__lang = lang
        self.__uid = uid

    def __getattr__(self, name):
        """This is the indexable wrapper getter for CPS,
        proxy try to get the repository document attributes,
        document in the repository hide some attributes to save some space."""
        vars = self.__vars
        if vars.has_key(name):
            return vars[name]
        ob = self.__ob
        proxy = None
        if isinstance(ob, ProxyBase):
            proxy = ob
            if name in ('getId', 'id', 'getPhysicalPath', 'uid', 'modified',
                        'getDocid', 'isCPSFolderish'):
                # These attributes are computed from the proxy
                pass
            else:
                # Use the repository document for remaining attributes
                ob_repo = ob.getContent(lang=self.__lang)
                if ob_repo is not None:
                     ob = ob_repo

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

    def path(self):
        """PathIndex needs a path attribute, otherwise it uses
        getPhysicalPath which fails for viewLanguage paths."""
        if self.__uid is not None:
            return self.__uid
        else:
            return self.__ob.getPhysicalPath()

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

    def position_in_container(self):
        """Return the object position in the container."""
        ob = self.__ob
        container = aq_parent(aq_inner(ob))
        if getattr(aq_base(container), 'getObjectPosition', None) is not None:
            try:
                return container.getObjectPosition(ob.getId())
            except ValueError, err:
                # Trying to index a doc before it is created ?
                self._cps_patch_logger.warning('position_in_container: '
                                               'got a ValueError %s', err)
                return 0
            except AttributeError, err:
                # Container without ordering support such as
                # BTreeFolder based folders. (proxy or not)
                self._cps_patch_logger.warning('position_in_container: '
                                               'got an AttributeError %s', err)
                return 0
        return 0

    def match_languages(self):
        """Return a list of languages that the proxy matches."""
        ob = self.__ob
        proxy_language = self.__lang
        if proxy_language is None:
            return ALL_LOCALES
        languages = [proxy_language]
        if ob.getDefaultLanguage() == proxy_language:
            languages.extend([lang for lang in ALL_LOCALES
                              if lang not in ob.getProxyLanguages()])
        return languages


### Patching CatalogTool methods
def cat_catalog_object(self, object, uid, idxs=[], update_metadata=1, pghandler=None):
    """Wraps the object before cataloging.

    Also takes into account multiple CPS languages.
    """

    # Don't index repository objects or anything under them.
    repotool = getToolByName(self, 'portal_repository', None)
    if repotool is not None and repotool.isObjectUnderRepository(object):
        return

    # BBB: for Zope 2.7, which doesn't take a pghandler
    if pghandler is None:
        pgharg = ()
    else:
        pgharg = (pghandler,)

    logger.log(TRACE, 'cat_catalog_object: index uid %s  obj %s', uid, object)
    wf = getattr(self, 'portal_workflow', None)
    if wf is not None:
        vars = wf.getCatalogVariablesFor(object)
    else:
        vars = {}

    # Filter out invalid indexes.
    if idxs != []:
        idxs = [i for i in idxs if self._catalog.indexes.has_key(i)]

    # Not a proxy.
    if not isinstance(object, ProxyBase):
        w = IndexableObjectWrapper(vars, object)
        ZCatalog.catalog_object(self, w, uid, idxs, update_metadata, *pgharg)
        return

    # Proxy with a viewLanguage uid.
    # Happens when the catalog is reindexed (refreshCatalog)
    # or when called by reindexObjectSecurity.
    path = uid.split('/')
    if KEYWORD_VIEW_LANGUAGE in path:
        if path.index(KEYWORD_VIEW_LANGUAGE) == len(path)-2:
            lang = path[-1]
        else:
            # Weird, but don't crash
            lang = None
        w = IndexableObjectWrapper(vars, object, lang, uid)
        ZCatalog.catalog_object(self, w, uid, idxs, update_metadata, *pgharg)
        return

    # We reindex a normal proxy.
    # Find what languages are in the catalog for this proxy
    uid_view = uid+'/'+KEYWORD_VIEW_LANGUAGE
    had_languages = []
    for brain in self.unrestrictedSearchResults(path=uid_view):
        path = brain.getPath()
        had_languages.append(path[path.rindex('/')+1:])

    # Do we now have only one language?
    languages = object.getProxyLanguages()
    if len(languages) == 1:
        # Remove previous languages
        for lang in had_languages:
            self.uncatalog_object(uid_view+'/'+lang)
        # Index normal proxy
        w = IndexableObjectWrapper(vars, object)
        ZCatalog.catalog_object(self, w, uid, idxs, update_metadata, *pgharg)
        return

    # We now have several languages (or none).
    # Remove old base proxy path
    if self._catalog.uids.has_key(uid):
        self.uncatalog_object(uid)
    # Also remove old languages
    for lang in had_languages:
        if lang not in languages:
            self.uncatalog_object(uid_view+'/'+lang)
    # Index all available translations of the proxy
    # with uid/viewLanguage/language for path
    for lang in languages:
        uid = uid_view + '/' + lang
        w = IndexableObjectWrapper(vars, object, lang, uid)
        ZCatalog.catalog_object(self, w, uid, idxs, update_metadata, *pgharg)


CatalogTool.catalog_object = cat_catalog_object
logger.log(TRACE, "Patching CMF CatalogTool.catalog_object")

#XXX should be a patch of uncatalog_object
def cat_unindexObject(self, object):
    """Remove from catalog."""

    # Documents from repository are not in catalog.
    # Unindexing produces an error
    if getToolByName(self, 'portal_repository').isObjectInRepository(object):
        logger.debug("unindexObject: ignored object from repository %s", object)
        return

    default_uid = self._CatalogTool__url(object)
    proxy = None
    if isinstance(object, ProxyBase):
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
logger.log(TRACE, "Patching CMF CatalogTool.unindexObject")


def cat_listAllowedRolesAndUsers(self, user):
    """Returns a list with all roles this user has + the username"""
    return getAllowedRolesAndUsersOfUser(user)

CatalogTool._listAllowedRolesAndUsers = cat_listAllowedRolesAndUsers
logger.log(TRACE, "Patching CMF CatalogTool._listAllowedRolesAndUsers")

# Adding an 'export' tab in ZMI (view defined in CPSUtil)
old_options = CatalogTool.manage_options
CatalogTool.manage_options = old_options + (
        {'label': 'Export', 'action': 'manage_genericSetupExport.html'},
        )
