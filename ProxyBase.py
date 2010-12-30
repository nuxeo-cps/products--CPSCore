# (C) Copyright 2002-2007 Nuxeo SAS <http://nuxeo.com>
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

import os
import math
from logging import getLogger
from types import DictType
import re
try:
    import PIL.Image
    PIL_OK = True
except ImportError:
    getLogger('Products.CPSCore').warn(
        "No PIL library found: no new image resizing will be done")
    PIL_OK = False

from zExceptions import BadRequest
from ExtensionClass import Base
from cPickle import Pickler, Unpickler
from cStringIO import StringIO
import tempfile
from zipfile import ZipFile
from struct import pack, unpack
from ComputedAttribute import ComputedAttribute
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo
from AccessControl import Unauthorized
import Acquisition
from Acquisition import aq_base, aq_parent, aq_inner
from OFS.SimpleItem import Item
from OFS.Folder import Folder
from OFS.Image import File, Image
from OFS.Traversable import Traversable
from webdav.WriteLockInterface import WriteLockInterface

import zope.interface
from Products.CPSCore.interfaces import ICPSProxy

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import View
from Products.CMFCore.permissions import ModifyPortalContent
from Products.CMFCore.permissions import ViewManagementScreens
from Products.CPSCore.permissions import ViewArchivedRevisions
from Products.CPSCore.permissions import ChangeSubobjectsOrder
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

from Products.CPSUtil.timeoutcache import getCache
from Products.CPSUtil.file import ofsFileHandler
from Products.CPSUtil.image import parse_size_spec
from Products.CPSUtil.integration import isUserAgentMsie
from Products.CPSCore.utils import KEYWORD_DOWNLOAD_FILE, \
     KEYWORD_ARCHIVED_REVISION, KEYWORD_SWITCH_LANGUAGE, \
     KEYWORD_VIEW_LANGUAGE, KEYWORD_VIEW_ZIP, SESSION_LANGUAGE_KEY, \
     REQUEST_LANGUAGE_KEY, KEYWORD_SIZED_IMAGE, IMAGE_RESIZING_CACHE
from Products.CPSCore.utils import bhasattr
from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.CPSBase import CPSBaseFolder
from Products.CPSCore.CPSBase import CPSBaseDocument
from Products.CPSCore.CPSBase import CPSBaseBTreeFolder
from Products.CPSCore.utils import walk

from Products.CPSCore.IndexationManager import get_indexation_manager
from Products.CPSCore.IndexationManager import ACTION_UNINDEX
from Products.CPSCore.IndexationManager import ACTION_INDEX
from Products.CPSCore.IndexationManager import ACTION_REINDEX


PROBLEMATIC_FILES_SUFFIXES = ('.exe',)
# OG: Old versions (1.1.x) of OpenOffice IE plugin also had a problem opening
# those files with authenticated sessions (see below). As the new version
# (2.0.x) works alright, the zip workaround is now deactivated. To reactivate
# it, uncomment the following line:
#PROBLEMATIC_FILES_SUFFIXES = ('.exe', '.sxw', '.sxc')

CACHE_ZIP_VIEW_KEY = 'CPS_ZIP_VIEW'
CACHE_ZIP_VIEW_TIMEOUT = 7200           # time to cache in second

logger = getLogger(__name__)

class ProxyBase(Base):
    """Mixin class for proxy types.

    A proxy stores:

    - docid, the document family it points to.

    - language_revs, a mapping of language -> revision. The revision is
      an integer representing a single revision of a document.

    - tag, an optional integer tag. A tag is an abstract reference to
      the mapping language -> revision. It is used to provide branch
      lineage between proxies. """

    zope.interface.implements(ICPSProxy)

    security = ClassSecurityInfo()
    use_mcat = 0

    def __init__(self, docid=None, default_language=None, language_revs=None,
                 from_language_revs=None, tag=None):
        self._docid = docid
        self._default_language = default_language
        self._language_revs = language_revs or {}
        self._from_language_revs = from_language_revs or {}
        self._tag = None

    #
    # API
    #

    # XXX was def getRepoId(self):
    security.declareProtected(View, 'getDocid')
    def getDocid(self):
        """Get the docid for this proxy."""
        return self._docid

    security.declarePrivate('setDocid')
    def setDocid(self, docid):
        """Set the docid of a proxy.

        (Used when proxies are unshared.)
        """
        self._docid = docid

    security.declareProtected(View, 'getLanguage')
    def getLanguage(self, lang=None):
        """Get the current language for the proxy."""
        pxtool = getToolByName(self, 'portal_proxies')
        return pxtool.getBestRevision(self, lang=lang)[0]

    security.declareProtected(View, 'getDefaultLanguage')
    def getDefaultLanguage(self):
        """The language to default to when there is no other choice.

        This is the language with which the proxy has firt been created.
        """
        return self._default_language

    security.declarePrivate('setDefaultLanguage')
    def setDefaultLanguage(self, default_language):
        """Set the default language for this proxy."""
        # Called by CPSWorkflow after creating an empty proxy.
        self._default_language = default_language

    # XXX was def getVersionInfos(self):
    security.declareProtected(View, 'getLanguageRevisions')
    def getLanguageRevisions(self):
        """Get the mapping of language -> revision."""
        return self._language_revs.copy()

    security.declarePrivate('_getLanguageRevisions')
    def _getLanguageRevisions(self):
        """Get the mapping of language -> revision, without copy.

        (Called by ProxyTool.)
        """
        return self._language_revs

    security.declarePrivate('setLanguageRevision')
    def setLanguageRevision(self, lang, rev):
        """Set the revision for a language.

        Does not notify the event service.

        (Called by ProxyTool.)
        """
        self._p_changed = 1
        self._language_revs[lang] = rev

    security.declareProtected(View, 'getFromLanguageRevisions')
    def getFromLanguageRevisions(self):
        """Get the originating language mapping for this proxy.

        This is used by checkout and checkin mechanism to find what the
        origin of a given proxy is.
        """
        return self._from_language_revs.copy()

    security.declarePrivate('_getFromLanguageRevisions')
    def _getFromLanguageRevisions(self):
        """Get the originating language mapping for this proxy (no copy)."""
        return self._from_language_revs

    security.declarePrivate('setFromLanguageRevisions')
    def setFromLanguageRevisions(self, from_language_revs):
        """Set the originating language mapping for this proxy."""
        self._from_language_revs = from_language_revs

    security.declareProtected(View, 'getTag')
    def getTag(self):
        """Get the tag for this proxy, or None."""
        return self._tag

    security.declarePrivate('setTag')
    def setTag(self, tag):
        """Set the tag for this proxy."""
        self._tag = tag

    security.declareProtected(View, 'getRevision')
    def getRevision(self, lang=None):
        """Get the best revision for a proxy."""
        pxtool = getToolByName(self, 'portal_proxies')
        return pxtool.getBestRevision(self, lang=lang)[1]

    security.declareProtected(View, 'getContent')
    def getContent(self, lang=None, rev=None):
        """Get the content object referred to by this proxy.

        The returned object may depend on the current language.

        If rev is passed, this specific revision is returned.
        """
        return self._getContent(lang=lang, rev=rev)

    security.declareProtected(ModifyPortalContent, 'getEditableContent')
    def getEditableContent(self, lang=None):
        """Get the editable content object referred to by this proxy.

        The returned object may depend on the current language.
        """
        return self._getContent(lang=lang, editable=1)

    security.declarePrivate('_getContent')
    def _getContent(self, lang=None, rev=None, editable=0):
        """Get the content object, maybe editable.

        Returns an object acquisition-wrapped under the proxy itself,
        so that security is correctly inferred.
        """
        pxtool = getToolByName(self, 'portal_proxies')
        ob = pxtool.getContent(self, lang=lang, rev=rev, editable=editable)
        # Rewrapping plays havoc with absolute_url, but that's not a
        # problem as nobody should ever get the absolute_url of an
        # object in the repository. In the previous implementation
        # anyway you got URLs containing portal_repository/ which is bad
        # too.
        if ob is None:
            return None
        return aq_base(ob).__of__(self)

    security.declarePrivate('proxyChanged')
    def proxyChanged(self):
        """Do necessary notifications after a proxy was changed."""
        self.reindexObject()
        pxtool = getToolByName(self, 'portal_proxies')
        utool = getToolByName(self, 'portal_url')
        rpath = utool.getRelativeUrl(self)
        pxtool._modifyProxy(self, rpath) # XXX or directly event ?
        evtool = getEventService(self)
        evtool.notify('sys_modify_object', self, {})

    def __getitem__(self, name):
        """Transparent traversal of the proxy to the real subobjects.

        Used for skins that don't take proxies enough into account.
        Returns an object wrapped in the acquisition context of the proxy.

        Parses URL revision switch of the form:
          mydoc/archivedRevision/n/...

        Parses URL translation switch of the form:
          mydoc/switchLanguage/<lang>/...

        Parses URLs for download of the form:
          mydoc/downloadFile/attrname/mydocname.pdf
        """
        if name == KEYWORD_ARCHIVED_REVISION:
            if self.isProxyArchived():
                raise KeyError(name)
            switcher = RevisionSwitcher(self)
            return switcher.__of__(self)
        elif name == KEYWORD_SWITCH_LANGUAGE:
            if self.isProxyArchived():
                raise KeyError(name)
            switcher = LanguageSwitcher(self)
            return switcher.__of__(self)
        elif name == KEYWORD_VIEW_LANGUAGE:
            if self.isProxyArchived():
                raise KeyError(name)
            viewer = LanguageViewer(self)
            return viewer.__of__(self)
        if getattr(self, name, None) is not None:
            # Acquire skins first, needed in Zope >= 2.9.5
            return getattr(self, name)
        ob = self._getContent()
        if ob is None:
            raise KeyError(name)
        if name == KEYWORD_DOWNLOAD_FILE:
            downloader = FileDownloader(ob, self)
            return downloader.__of__(self)
        if name == KEYWORD_SIZED_IMAGE:
            downloader = ImageDownloader(ob, self)
            return downloader.__of__(self)
        elif name == KEYWORD_VIEW_ZIP:
            zipview = ViewZip(ob, self)
            return zipview.__of__(self)
        try:
            res = getattr(ob, name)
        except AttributeError:
            try:
                res = ob[name]
            except (KeyError, IndexError, TypeError, AttributeError):
                raise KeyError, name
        return res

    #
    # Freezing
    #

    security.declareProtected(ModifyPortalContent, 'freezeProxy')
    def freezeProxy(self, REQUEST=None):
        """Freeze the proxy.

        Freezing means that any attempt at modification will create a new
        revision. This allows for lazy copying.

        (Called by CPSWorkflow.)
        """
        if REQUEST is not None:
            raise Unauthorized('Not allowed through the web')
        pxtool = getToolByName(self, 'portal_proxies')
        self._freezeProxy(self, pxtool)

    security.declarePrivate('_freezeProxy')
    def _freezeProxy(self, ob, pxtool):
        """Freeze the proxy."""
        # XXX use an event?
        pxtool.freezeProxy(self)

    security.declarePublic('isProxyArchived')
    def isProxyArchived(self):
        """Is the proxy archived. False."""
        return 0

    #
    # Staging
    #

    security.declarePrivate('serializeProxy')
    def serializeProxy(self):
        """Serialize the proxy, without subobjects.

        Assumes no persistent attributes.
        Assumes a normal ObjectManager with _objects.
        Does NOT export subobjects from objectValues().
        """
        # skip subobjects
        skipids = self.objectIds()
        skipids.append('_objects')
        # other skipped ids
        skipids.extend(['_owner',
                        'workflow_history', # is persistent...
                        ])
        # ok ids
        okids = ['id',
                 'portal_type',
                 '_properties',
                 '__ac_local_roles__',
                 '__ac_local_group_roles__',
                 # proxy definition
                 '_docid',
                 '_default_language',
                 '_language_revs',
                 '_from_language_revs',
                 '_tag',
                 # dublin core
                 'title',
                 'description',
                 'subject',
                 'creation_date',
                 'modification_date',
                 'effective_date',
                 'expiration_date',
                 'rights',
                 'format',
                 'language',
                 'contributors',
                 ]
        # writable properties are ok too
        for prop in self._properties:
            if 'w' in prop.get('mode', 'w'):
                okids.append(prop['id'])
        # extract
        stuff = {}
        for k, v in self.__dict__.items():
            if k in skipids:
                continue
            if k in okids:
                stuff[k] = v
                continue
            # security
            if k.startswith('_') and k.endswith('_Permission'):
                stuff[k] = v
                continue
            logger.debug("Warning: serialize of %s found unknown %s=%s",
                         self.getId(), k, v)
            stuff[k] = v # Serialize it anyway
        # now serialize stuff
        f = StringIO()
        p = Pickler(f, 1)
        p.dump(stuff)
        ser = f.getvalue()
        class_name = self.__class__.__name__
        return (pack('>I', len(class_name))
                +class_name
                +ser)

    #
    # Security
    #

    def _reindexObject(self, idxs=[]):
        """Called to reindex when the object has changed."""
        logger.debug("reindex idxs=%s for %s", idxs,
                     '/'.join(self.getPhysicalPath()))
        # Update the effective date
        # Optim: we only modify the effective_date if this is a global
        # reindexing, ie after the object has been modified,
        # and not in case of a catalog reindexing.
        if idxs == []:
            content = self._getContent()
            if content is not None:
                effective_date = self._getContent().effective_date
                self.effective_date = effective_date
        if 'allowedRolesAndUsers' in idxs:
            # Both must be updated
            idxs.append('localUsersWithRoles')
        return CMFCatalogAware.reindexObject(self, idxs=idxs)

    # overloaded
    def reindexObject(self, idxs=[]):
        """Schedule object for reindexation
        """
        get_indexation_manager().push(self, idxs=idxs, action=ACTION_REINDEX)

    # overloaded
    def indexObject(self):
        """Schedule object for indexing.
        """
        get_indexation_manager().push(self, idxs=[], action=ACTION_INDEX)

    # overloaded
    def unindexObject(self):
        """Schedule object for unindexing."""
        get_indexation_manager().push(self, action=ACTION_UNINDEX)

    def _reindexObjectSecurity(self, skip_self=False):
        """Called to security-related indexes."""
        logger.debug("reindex security for %s",
                     '/'.join(self.getPhysicalPath()))
        # Notify that this proxy's security has changed.
        # Listeners will have to recurse if necessary.
        # (The notification for the object repo is done by the repo.)
        evtool = getEventService(self)
        evtool.notify('sys_modify_security', self, {})
        return CMFCatalogAware.reindexObjectSecurity(self, skip_self)

    # overloaded
    def reindexObjectSecurity(self):
        get_indexation_manager().push(self, with_security=True)

    #
    # Helpers
    #

    security.declarePublic('Title')
    def Title(self):
        """The object's title."""
        title = ''
        ob = self.getContent()
        title = ob.Title()
        if self.use_mcat and title:
            translation_service = getToolByName(self, 'translation_service',
                                                None)
            if translation_service is not None:
                title = translation_service(msgid=title, default=title)
        return title

    security.declarePublic('title_or_id')
    def title_or_id(self):
        """The object's title or id."""
        return self.Title() or self.getId()

    security.declarePublic('SearchableText')
    def SearchableText(self):
        """No searchable text."""
        return ''

    def Type(self):
        """Dublin core Type."""
        # Used by main_template.
        ob = self.getContent()
        if ob is not None:
            return ob.Type()
        else:
            return ''

    security.declarePublic('getProxyLanguages')
    def getProxyLanguages(self):
        """Return all available languages."""
        return self._getLanguageRevisions().keys()

    #
    # Helper for I18n catalog
    #
    security.declarePrivate('_getAllMCatalogTranslation')
    def _getAllMCatalogTranslation(self, msgid):
        """Return a dict of message catalog translation."""
        translation_service = getToolByName(self, 'translation_service', None)
        if translation_service is None:
            return {'en': msgid}
        ret = {}
        for locale in translation_service.getSupportedLanguages():
            ret[locale] = translation_service(msgid=msgid,
                                              target_language=locale,
                                              default=msgid)
        return ret

    security.declareProtected(View, 'getL10nTitles')
    def getL10nTitles(self):
        """Return a dict of title in all available languages.

        This is used for catalog metadata, see the indexableWrapperObject
        to understand how it is used as metadata."""
        ret = {}
        if self.use_mcat:
            title = self.getContent().Title()
            ret = self._getAllMCatalogTranslation(title)
        else:
            for locale in self.getProxyLanguages():
                ob = self.getContent(lang=locale)
                ret[locale] = ob.Title()
        return ret

    security.declareProtected(View, 'getL10nDescriptions')
    def getL10nDescriptions(self):
        """Return a dict of description in all available languages.

        This is used for catalog metadata."""
        ret = {}
        if self.use_mcat:
            desc = self.getContent().Description()
            ret = self._getAllMCatalogTranslation(desc)
        for locale in self.getProxyLanguages():
            ob = self.getContent(lang=locale)
            ret[locale] = ob.Description()
        return ret

    security.declareProtected(View, 'isDefaultLanguage')
    def isDefaultLanguage(self):
        """Return 1 if proxy is the default language proxy.

        This is used as catalog index."""
        if self.getLanguage() == self.getDefaultLanguage():
            return 1
        return 0

    #
    # Helper for proxy folderish documents
    #
    security.declareProtected(View, 'isOutsideProxyFolderishDocument')
    def isOutsideProxyFolderishDocument(self):
        """Returns true if outside any proxy folderish document."""
        container = aq_parent(aq_inner(self))
        if hasattr(container, 'thisProxyFolderishDocument'):
            return 0
        else:
            return 1

    security.declareProtected(View, 'isCPSFolderish')
    def isCPSFolderish(self):
        """Return True if the document is a structural folderish."""
        if not self.isPrincipiaFolderish:
            # structural document must be folderish
            return False
        ttool = getToolByName(self, 'portal_types')
        if getattr(ttool[self.portal_type],
                   'cps_display_as_document_in_listing', False):
            # this folderish document is not structural
            return False
        return True

    #
    # Revision management
    #

    security.declareProtected(ModifyPortalContent, 'revertToRevisions')
    def revertToRevisions(self, language_revs, freeze=1):
        """Revert this proxy to older revisions.

        If freeze=1 (default), freeze the current revisions.
        """
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool.revertProxyToRevisions(self, language_revs, freeze)

    security.declareProtected(ModifyPortalContent, 'delArchivedRevisions')
    def delArchivedRevisions(self, revs):
        """Delete some archived revisions of this proxy.
        """
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool.delProxyArchivedRevisions(self, revs)

    security.declareProtected(View, 'getArchivedInfos')
    def getArchivedInfos(self):
        """Get info about the archived revisions for this proxy.

        Returns a list of dicts with info:
          rev, lang, modified, rpaths, is_frozen

        (Called by user code to display a history.)
        """
        docid = self.getDocid()
        pxtool = getToolByName(self, 'portal_proxies')
        return pxtool.getArchivedInfosForDocid(docid)

    #
    # Translation helpers.
    #

    security.declareProtected(ModifyPortalContent, 'addLanguageToProxy')
    def addLanguageToProxy(self, lang, from_lang=None, REQUEST=None, *args,
                           **kw):
        """Add a new language."""
        if REQUEST is not None:
            raise Unauthorized("Not accessible TTW")
        pxtool = getToolByName(self, 'portal_proxies')
        rev = pxtool.createRevision(self, lang, from_lang, *args, **kw)
        return rev

    security.declareProtected(ModifyPortalContent, 'delLanguageFromProxy')
    def delLanguageFromProxy(self, lang, REQUEST=None):
        """Delete a language.

        Cannot delete the default language or the last remaining language.
        """
        if REQUEST is not None:
            raise Unauthorized("Not accessible TTW")
        if lang == self.getDefaultLanguage():
            raise ValueError("Cannot delete default language '%s'" % lang)
        language_revs = self._getLanguageRevisions()
        if not language_revs.has_key(lang):
            raise ValueError("Cannot delete invalid language '%s'" % lang)
        if len(language_revs) == 1:
            raise ValueError("Cannot delete last language '%s'" % lang)
        del language_revs[lang]
        self._language_revs = language_revs # XXX no setLanguageRevisions
        self.proxyChanged()

    #
    # ZMI
    #

    proxybase_manage_options = (
        {'label': 'Proxy',
         'action': 'manage_proxyInfo',
         },
        )

    security.declareProtected(ViewManagementScreens, 'manage_proxyInfo')
    manage_proxyInfo = DTMLFile('zmi/proxy_info', globals())

    _properties = (
        {'id':'PropDocid', 'type':'string', 'mode':''},
        {'id':'PropDefaultLanguage', 'type':'string', 'mode':''},
        {'id':'PropLanguageRevisions', 'type':'string', 'mode':''},
        {'id':'PropFromLanguageRevisions', 'type':'string', 'mode':''},
        {'id':'PropTag', 'type':'string', 'mode':''},
        )
    PropDocid = ComputedAttribute(getDocid, 1)
    PropDefaultLanguage = ComputedAttribute(getDefaultLanguage, 1)
    PropLanguageRevisions = ComputedAttribute(getLanguageRevisions, 1)
    PropFromLanguageRevisions = ComputedAttribute(getFromLanguageRevisions, 1)
    PropTag = ComputedAttribute(getTag, 1)

InitializeClass(ProxyBase)

class BaseDownloader(Acquisition.Explicit):
    """Common part of intermediate objects allowing for downloads."""

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    keyword = 'BaseDownloader should not appear'

    __implements__ = (WriteLockInterface,)

    url_parts = 2

    def __repr__(self):
        s = '<%s for %s' % (self.__class__.__name__, self.ob)
        if self.state > 0:
            s += '/'+self.attrname
        if self.state > 1 and self.url_parts > 2:
            s += '/' + self.additional
        if self.state == self.url_parts:
            s += '/' + self.filename
        s += '>'
        return s

    security.declareProtected(View, 'absolute_url')
    def absolute_url(self):
        url = self.proxy.absolute_url() + '/' + self.keyword
        if self.state > 0:
            url += '/' + self.attrname
        if self.state > 1 and self.url_parts > 2:
            url += '/' + self.additional
        if self.state == self.url_parts:
            url += '/' + self.filename
        return url

    def __init__(self, ob, proxy):
        """
        Init the Downloader with the document and proxy to which it pertains.

        ob is the document that owns the file and proxy is the proxy of this
        same document
        """
        self.ob = ob
        self.proxy = proxy
        self.state = 0
        self.attrname = None
        self.file = None
        self.filename = None
        self.additional = None # any relevant additional arg put in URL

    def __bobo_traverse__(self, request, name):
        state = self.state
        ob = self.ob
        if state == 0:
            # First call, swallow attribute
            file_ = self._getFile(ob, name)
            if file_ is not None and not isinstance(file_, File):
                logger.debug("Attribute '%s' is not a File but %s",
                             name, `file_`)
                raise KeyError(name)
            self.attrname = name
            self.file = file_
            self.state = 1
            return self
        elif state == 1 and self.url_parts > 2:
            # Got attribute, swallow additional
            self.additional = name
            self.state = 2
            return self
        elif state == self.url_parts - 1:
            # Got everything, swallow filename
            self.filename = name
            self.state = self.url_parts
            self.meta_type = getattr(self.file, 'meta_type', '')
            return self
        elif name in ('index_html', 'absolute_url', 'content_type',
                      'cache_clear',
                      'HEAD', 'PUT', 'LOCK', 'UNLOCK',):
            return getattr(self, name)
        else:
            raise KeyError(name)

    security.declareProtected(View, 'content_type')
    def content_type(self):
        if self.state != self.url_parts:
            return None
        return self.file.content_type

    security.declareProtected(View, 'HEAD')
    def HEAD(self, REQUEST, RESPONSE):
        """Retrieve the HEAD information for HTTP."""
        if self.state != self.url_parts:
            return None
        file = self.file
        if file is not None:
            return file.HEAD(REQUEST, RESPONSE)
        else:
            RESPONSE.setHeader('Content-Type', 'text/plain')
            RESPONSE.setHeader('Content-Length', '0')
            return ''

    def _getFile(self, document, name):
        if hasattr(aq_base(document), name):
            # fast: usually file is stored as a subobject by the storage
            # adapter
            return getattr(document, name)
        else:
            # make it work when file is computed by a field read expression
            return document.getDataModel(proxy=self.proxy)[name]

InitializeClass(BaseDownloader)


class FileDownloader(BaseDownloader):
    """Intermediate object allowing for file download.

   Returned by a proxy during traversal of .../downloadFile/.

    Parses URLs of the form .../downloadFile/attrname/mydocname.pdf
    """

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    logger = getLogger('CPSCore.ProxyBase.FileDownloader')

    keyword = KEYWORD_DOWNLOAD_FILE

    url_parts = 2

    security.declareProtected(View, 'index_html')
    def index_html(self, REQUEST, RESPONSE):
        """Publish the file or image."""
        if self.state != 2:
            return None
        file = self.file
        if file is not None:
            file_basename, file_suffix = os.path.splitext(self.filename)
            # This code is here to allow MSIE, and potentially other browsers,
            # to retrieve some files as ZIP archives, eg. without using its
            # plugins since those plugins may fail in some circumstances.
            if (isUserAgentMsie(REQUEST) and
                file_suffix in PROBLEMATIC_FILES_SUFFIXES):
                RESPONSE.setHeader('Content-Type', 'application/zip')
                RESPONSE.setHeader('Content-disposition',
                                   'attachment; filename=%s%s'
                                   % (file_basename, '.zip'))
                fd, archive_filepath = tempfile.mkstemp(suffix='.zip')
                archive_file = ZipFile(archive_filepath, 'w')
                archive_file.writestr(self.filename, str(file))
                os.close(fd)
                archive_file = open(archive_filepath, 'r')
                out = archive_file.read()
                archive_file.close()
                os.unlink(archive_filepath)
                return out

            return file.index_html(REQUEST, RESPONSE)
        else:
            RESPONSE.setHeader('Content-Type', 'text/plain')
            RESPONSE.setHeader('Content-Length', '0')
            return ''

    # Attribut checked by ExternalEditor to know if it can "WebDAV" on this
    # object.
    def EditableBody(self):
        if self.state != 2:
            return None
        file = self.file
        if file is not None:
            return str(self.file.data)

    security.declareProtected(ModifyPortalContent, 'PUT')
    def PUT(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) PUT requests (WebDAV)."""
        self.logger.debug("PUT()")
        if self.state != 2:
            self.logger.debug("BadRequest: Cannot PUT with state != 2")
            raise 'BadRequest', "Cannot PUT with state != 2"
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        response = file_.PUT(REQUEST, RESPONSE)
        # If the considered document is a CPSDocument we must use the edit()
        # method since this method does important things such as setting dirty
        # flags on modified fields.
        # XXX: Note that using edit() modifies the file attribute twice.
        # We shouldn't use the file.PUT() method but it is helpful to get the
        # needed response object.
        if getattr(aq_base(document), '_has_generic_edit_method', 0):
            document.edit({self.attrname: file_}, proxy=self.proxy)
        return response

    security.declareProtected(ModifyPortalContent, 'LOCK')
    def LOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) LOCK requests (WebDAV)."""
        self.logger.debug("LOCK()")
        if self.state != 2:
            self.logger.debug("BadRequest: Cannot LOCK with state != 2")
            raise 'BadRequest', "Cannot LOCK with state != 2"
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.LOCK(REQUEST, RESPONSE)

    security.declareProtected(ModifyPortalContent, 'UNLOCK')
    def UNLOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) UNLOCK requests (WebDAV)."""
        self.logger.debug("UNLOCK()")
        if self.state != 2:
            self.logger.debug("BadRequest: Cannot UNLOCK with state != 2")
            raise 'BadRequest', "Cannot UNLOCK with state != 2"
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.UNLOCK(REQUEST, RESPONSE)

    def wl_lockValues(self, killinvalids=0):
        """Handle HTTP (and presumably FTP?) wl_lockValues requests (WebDAV)."""
        self.logger.debug("wl_lockValues()")
        if self.state != 2:
            self.logger.debug("BadRequest: Cannot wl_lockValues with state != 2")
            raise 'BadRequest', "Cannot wl_lockValues with state != 2"
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.wl_lockValues(killinvalids)

    def wl_isLocked(self):
        """Handle HTTP (and presumably FTP?) wl_isLocked requests (WebDAV)."""
        self.logger.debug("wl_isLocked()")
        if self.state != 2:
            self.logger.debug("BadRequest: Cannot wl_isLocked with state != 2")
            raise 'BadRequest', "Cannot wl_isLocked with state != 2"
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.wl_isLocked()

InitializeClass(FileDownloader)

IMG_SZ_FULLSPEC_REGEXP = re.compile(r'^(\d+)x(\d+)$')
IMG_SZ_HEIGHT_REGEXP = re.compile(r'^h(\d+)$')
IMG_SZ_WIDTH_REGEXP = re.compile(r'^w(\d+)$')
IMG_SZ_LARGEST_REGEXP = re.compile(r'^l(\d+)$')

class ImageDownloader(BaseDownloader):
    """Intermediate object allowing for image download with resizing.

    Returned by a proxy during traversal of .../sizedImg/.

    Parses URLs of the form .../sizedImg/size/myimg.jpg, where size can be
       - full: untransformed
       - 320x200: full size spec (width plus height)
       - w320: width spec: height will keep aspect ratio
       - h200: height spec: width will keep aspect ratio
       - l540: largest dimension spec: wished size of the largest dimension,
                                       keeping aspect ratio

    Only 'full' allowed for content-changing requests.
    Any non compliant spec or method should raise BadRequest
    """

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    logger = getLogger('CPSCore.ProxyBase.FileDownloader')

    keyword = KEYWORD_SIZED_IMAGE

    url_parts = 3

    security.declareProtected(View, 'isFullSize')
    def isFullSize(self):
        return self.state == self.url_parts and self.additional == 'full'

    def assertFullSize(self, meth_name='METH'):
        if self.isFullSize():
            return
        self.logger.debug(
            "BadRequest: cannot %s (state=%d, additional=%s)",
            self.state, self.additional)
        raise BadRequest("Cannot %s on incomplete or resizing URL" % meth_name)

    security.declareProtected(View, 'index_html')
    def index_html(self, REQUEST, RESPONSE):
        """Publish the file or image."""
        if self.state != self.url_parts:
            return None
        img = self.getImage()
        if img is not None:
            return img.index_html(REQUEST, RESPONSE)
        else:
            RESPONSE.setHeader('Content-Type', 'text/plain')
            RESPONSE.setHeader('Content-Length', '0')
            return ''

    def geometryFromLargest(self, size):
        """Compute width, height from the wished largest dimension."""
        img = self.file
        srcw, srch = img.width, img.height
        if srcw > srch:
            return size, self.heightFromWidth(size)
        else:
            return self.widthFromHeight(size), size

    def heightFromWidth(self, size):
        """Deduce target height from wished width keeping aspect ratio."""
        srcw, srch = self.srcGeometry()
        return int(math.floor(srch * float(size)/srcw + 0.5))

    def widthFromHeight(self, size):
        """Deduce target width from wished height keeping aspect ratio."""
        srcw, srch = self.srcGeometry()
        return int(math.floor(srcw * float(size)/srch + 0.5))

    def srcGeometry(self):
        """Return width, height for the orignal image."""
        # 24 bytes are always supposed to be in the first range
        # Pdata implement slices
        fileio = ofsFileHandler(self.file)
        try:
            img = PIL.Image.open(fileio)
            return img.size
        except: # TODO a lot
            return -1, -1

    def targetGeometry(self):
       spec = self.additional
       sz = parse_size_spec(spec)
       if isinstance(sz, int):
           return self.geometryFromLargest(sz)

       w, h = sz
       if w is None:
           return self.widthFromHeight(h), h
       elif h is None:
           return w, self.heightFromWidth(w)

       return w, h


    security.declareProtected(View, 'getImage')
    def getImage(self):
       """Get the image with appropriate size.
       Supports persistent cache.
       TODO: security hazard, someone could inflate ZODB simply by requesting
       lots and lots of different ones: clean the oldest ones
       TODO move the actual image processing to CPSUtil
       """
       orig = self.file
       if self.additional == 'full':
           return orig

       if not self.ob.hasObject(IMAGE_RESIZING_CACHE):
           # no events because the catalog hook can lead to ConflictError
           # if lots of first time requests in parallel.
           # in this case, indexing is useless, really
           self.ob._setObject(IMAGE_RESIZING_CACHE,
                              Folder(IMAGE_RESIZING_CACHE),
                              suppress_events=True)

       cache = getattr(self.ob, IMAGE_RESIZING_CACHE)

       w, h = self.targetGeometry()

       key = '%s-%dx%d' % (self.attrname, w, h)

       pm = orig._p_mtime
       orig_last_mod = orig._p_mtime
       if orig_last_mod is not None: # not commited
           orig_last_mod = long(orig_last_mod)

       if cache.hasObject(key):
           existing = cache[key]
           ex_last_mod = existing._p_mtime
           if orig_last_mod is None:
               if ex_last_mod is None:
                   # both non commited: case should appear in unit tests only
                   return existing
           else:
               ex_last_mod = long(ex_last_mod)
               if ex_last_mod >= orig_last_mod:
                   return existing
           # existing can't be served, purge it
           cache._delObject(key)

       resized = self.resize(w, h, key)
       if resized is None: # failed for some reason, fallback
           return orig

       return self.setInCache(cache, resized)

    security.declarePrivate('setInCache')
    @classmethod
    def setInCache(self, cache, img):
        """Set in cache and do the housekeeping.

        Keeps no more than 10 objects in cache. For different sizes of an image
        that should be more than enough, and this protects against buggy or
        malicious requests.
        """

        cache_ids = cache.objectIds()
        if len(cache_ids) > 9: # len(cache) wouldn't work
            oldest = None
            for oid, ob in cache.objectItems():
                ob_time = ob._p_mtime
                if ob_time is None: # so recent it's uncommited
                    continue
                if oldest is None or ob_time < oldest:
                    oldest = ob_time
                    todel = oid

            if oldest is None: # 10 existing, all uncommited, not really normal
                todel = cache_ids[0]

            cache._delObject(todel)

        cache._setObject(img.getId(), img)
        return img

    security.declarePrivate('resize')
    def resize(self, width, height, resized_id):
        """Return OFS.Image.Image or None if cannot resize."""

        self.logger.info("Computing %r for %s.", resized_id, self.ob)
        if not PIL_OK:
            self.logger.warn("Resizing can't be done until PIL is installed")
            return

        fileio = ofsFileHandler(self.file)
        try:
            img = PIL.Image.open(fileio)
            newimg = img.resize((width, height), PIL.Image.ANTIALIAS)
            outfile = StringIO()
            newimg.save(outfile, format=img.format)
        except (NameError, IOError, ValueError, SystemError), err:
                self.logger.warning(
                    "Failed to resize image %r at %r (%s), "
                    "full size will be served",
                    self.filename, self.attrname, err)
                return

        return Image(resized_id, self.file.title, outfile)

    @classmethod
    def makeSizeSpec(self, height=0, width=0, largest=0):
        """ Create a size specification.

        >>> ImageDownloader.makeSizeSpec(height=200)
        'h200'
        >>> ImageDownloader.makeSizeSpec(width=320)
        'w320'
        >>> ImageDownloader.makeSizeSpec(width=320, height=200)
        '320x200'
        >>> ImageDownloader.makeSizeSpec(largest=800)
        'l800'
        >>> ImageDownloader.makeSizeSpec()
        'full'
        """
        if largest and height and width:
            raise ValueError("Specifying all of largest, height and width "
                             "is a contradiction")
        elif largest:
            return 'l%d' % largest
        elif width and height:
            return '%dx%d' % (width, height)
        elif width:
            return 'w%d' % width
        elif height:
            return 'h%d' % height
        return 'full'

    @classmethod
    def makeSizeUriPart(cls, attr, height=0, width=0, largest=0):
        """Return the part or URI that will trigger appropriate resizing."""
        # split in half to avoid testing the constant
        spec = cls.makeSizeSpec(height=height, width=width, largest=largest)
        return '/'.join((KEYWORD_SIZED_IMAGE, attr, spec))

    # Attribut checked by ExternalEditor to know if it can "WebDAV" on this
    # object.
    def EditableBody(self):
        if not self.isFullSize():
            return None
        file = self.file
        if file is not None:
            return str(self.file.data)

    security.declareProtected(ModifyPortalContent, 'PUT')
    def PUT(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) PUT requests (WebDAV)."""
        self.assertFullSize(meth_name='PUT')
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        response = file_.PUT(REQUEST, RESPONSE)
        # If the considered document is a CPSDocument we must use the edit()
        # method since this method does important things such as setting dirty
        # flags on modified fields.
        # XXX: Note that using edit() modifies the file attribute twice.
        # We shouldn't use the file.PUT() method but it is helpful to get the
        # needed response object.
        if getattr(aq_base(document), '_has_generic_edit_method', 0):
            document.edit({self.attrname: file_}, proxy=self.proxy)
        return response

    security.declareProtected(ModifyPortalContent, 'LOCK')
    def LOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) LOCK requests (WebDAV)."""
        self.assertFullSize(meth_name='LOCK')
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.LOCK(REQUEST, RESPONSE)

    security.declareProtected(ModifyPortalContent, 'UNLOCK')
    def UNLOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) UNLOCK requests (WebDAV)."""
        self.assertFullSize(meth_name='UNLOCK')
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.UNLOCK(REQUEST, RESPONSE)

    def wl_lockValues(self, killinvalids=0):
        """Handle HTTP (and presumably FTP?) wl_lockValues requests (WebDAV)."""
        self.assertFullSize(meth_name='wl_lockValues')
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.wl_lockValues(killinvalids)

    def wl_isLocked(self):
        """Handle HTTP (and presumably FTP?) wl_isLocked requests (WebDAV)."""
        self.assertFullSize(meth_name='wl_isLocked')
        document = self.proxy.getEditableContent()
        file_ = self._getFile(document, self.attrname)
        return file_.wl_isLocked()

InitializeClass(ImageDownloader)


class LanguageSwitcher(Acquisition.Explicit):
    """Language Switcher.

    Use a session flag to keep a proxy into a selected locale."""

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    # Never viewable, so skipped by breadcrumbs.
    _View_Permission = ()

    def __init__(self, proxy):
        self.proxy = proxy
        self.id = KEYWORD_SWITCH_LANGUAGE

    def __repr__(self):
        return '<LanguageSwitcher for %s>' % repr(self.proxy)

    def __bobo_traverse__(self, REQUEST, lang):
        proxy = self.proxy
        utool = getToolByName(self, 'portal_url')
        rpath = utool.getRelativeUrl(proxy)
        # store information by the time of the request to change the
        # language used for viewing the current document,
        # bypassing translation_service
        if REQUEST is not None:
            if not REQUEST.has_key('SESSION'):
                # unrestricted traverse pass a fake REQUEST without SESSION
                REQUEST = getattr(self.proxy, 'REQUEST')
            if REQUEST.has_key('SESSION'):
                langswitch = REQUEST.SESSION.get(SESSION_LANGUAGE_KEY, {})
                langswitch[rpath] = lang
                REQUEST.SESSION[SESSION_LANGUAGE_KEY] = langswitch
        #  Return the proxy in the context of the container
        container = aq_parent(aq_inner(proxy))
        return proxy.__of__(container)

InitializeClass(LanguageSwitcher)


class LanguageViewer(Acquisition.Explicit):
    """Language Viewer.

    Use a REQUEST variable to keep a temporary selected locale."""

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    # Never viewable, so skipped by breadcrumbs.
    _View_Permission = ()

    def __init__(self, proxy):
        self.proxy = proxy
        self.id = KEYWORD_SWITCH_LANGUAGE

    def __repr__(self):
        return '<LanguageViewer for %s>' % repr(self.proxy)

    def __bobo_traverse__(self, REQUEST, lang):
        proxy = self.proxy
        utool = getToolByName(self, 'portal_url')
        rpath = utool.getRelativeUrl(proxy)
        # store information by the time of the request to change the
        # language used for viewing the current document, bypassing
        # translation_service
        if REQUEST is not None:
            langswitch = REQUEST.get(REQUEST_LANGUAGE_KEY, {})
            langswitch[rpath] = lang
            if isinstance(REQUEST, DictType):
                # unrestrictedtraverse use a fake REQUEST
                REQUEST = getattr(self.proxy, 'REQUEST')
            REQUEST.set(REQUEST_LANGUAGE_KEY, langswitch)
        # Return the proxy in the context of the container
        container = aq_parent(aq_inner(proxy))
        return proxy.__of__(container)

    # Needed by brain.getObject in Zope >= 2.7.6
    getPhysicalRoot = Acquisition.Acquired
    unrestrictedTraverse = Traversable.unrestrictedTraverse.im_func
    restrictedTraverse = Traversable.restrictedTraverse.im_func

InitializeClass(LanguageViewer)



class RevisionSwitcher(Acquisition.Explicit):
    """Intermediate object allowing for revision choice.

    Returned by a proxy during traversal of .../archivedRevision/.

    Parses URLs of the form .../archivedRevision/n/...
    """

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    # Never viewable, so skipped by breadcrumbs.
    _View_Permission = ()

    logger = getLogger("CPSCore.ProxyBase.RevisionSwitcher")

    def __init__(self, proxy):
        self.proxy = proxy
        self.id = KEYWORD_ARCHIVED_REVISION

    def __repr__(self):
        return '<RevisionSwitcher for %s>' % `self.proxy`

    def __bobo_traverse__(self, request, rev):
        try:
            rev = int(rev)
        except ValueError:
            self.logger.debug("Invalid revision %r", rev)
            raise KeyError(rev)

        proxy = self.proxy
        docid = proxy._docid
        pxtool = getToolByName(proxy, 'portal_proxies')
        ob = pxtool.getContentByRevision(docid, rev)
        if ob is None:
            self.logger.debug("Unknown revision %s", rev)
            raise KeyError(rev)

        # Find language
        base_ob = aq_base(ob)
        if hasattr(base_ob, 'Language'):
            lang = ob.Language()
        elif hasattr(base_ob, 'language'):
            lang = ob.language
        else:
            lang = proxy._default_language

        revproxy = VirtualProxy(ob, docid, rev, lang)
        revproxy._setId(KEYWORD_ARCHIVED_REVISION+'/'+str(rev))

        return revproxy.__of__(proxy)

InitializeClass(RevisionSwitcher)


class VirtualProxy(ProxyBase, CPSBaseDocument):
    """Virtual proxy used for revision access.

    Provides access to a fixed revision.
    """

    security = ClassSecurityInfo()
    security.declareObjectProtected(ViewArchivedRevisions)

    # Never modifiable.
    _Modify_portal_content_Permission = ()

    def __init__(self, ob, docid, rev, lang):
        self._ob = ob

        self._docid = docid
        self._default_language = lang
        self._language_revs = {lang: rev}
        self._from_language_revs = {}
        self._tag = None

        self.portal_type = ob.portal_type
        # No workflow state.

    security.declarePrivate('_getContent')
    def _getContent(self, lang=None, rev=None, editable=0):
        """Get the content object, maybe editable."""
        if editable:
            raise ValueError("Cannot get editable version of a virtual proxy")
        if lang is not None:
            raise ValueError("Cannot specify lang for a virtual proxy")
        if rev is not None:
            raise ValueError("Cannot specify rev for a virtual proxy")
        # Wrap in the virtual proxy, which is wrapped in the real proxy,
        # to get proper security context.
        return aq_base(self._ob).__of__(self)

    security.declareProtected(View, 'getLanguage')
    def getLanguage(self, lang=None):
        """Get the language for the virtual proxy."""
        return self._default_language

    security.declareProtected(View, 'getRevision')
    def getRevision(self, lang=None):
        """Get the revision for the virtual proxy."""
        return self._language_revs.values()[0]

    security.declarePublic('isProxyArchived')
    def isProxyArchived(self):
        """Is the proxy archived. True."""
        return 1

InitializeClass(VirtualProxy)

# initialize zip_cache to store unzipped documents
zip_cache = getCache(CACHE_ZIP_VIEW_KEY)
zip_cache.setTimeout(CACHE_ZIP_VIEW_TIMEOUT)

class ViewZip(Acquisition.Explicit):
    """Intermediate object allowing to view zipped content

    TODO subclass BaseDownloader to stop duplication and make unit tests
    Returned by a proxy during traversal of .../viewZip/.

    Parses URLs of the form .../viewZip/attrname/mydocname.zip/path/in/archive
    the content is cached using a TimeoutCache.
    """
    security = ClassSecurityInfo()
    security.declareObjectPublic()

    logger = getLogger('CPSCore.ProxyBase.ViewZip')

    def __init__(self, ob, proxy):
        """
        Init the ViewZip with the document and proxy to which it pertains.

        ob is the document that owns the file and proxy is the proxy of this
        same document
        """
        self.ob = ob
        self.proxy = proxy
        self.state = 0
        self.attrname = None
        self.file = None
        self.filepath = []

    def __repr__(self):
        s = '<ViewZip for %s' % `self.ob`
        if self.state > 0:
            s += '/'+self.attrname
        if self.state > 1:
            s += '/'+ '/'.join(self.filepath)
        s += '>'
        return s

    def __bobo_traverse__(self, request, name):
        state = self.state
        ob = self.ob
        if state == 0:
            # First call, swallow attribute which should be a zipfile
            if not hasattr(aq_base(ob), name):
                self.logger.debug("Not a base attribute: '%s'", name)
                raise KeyError(name)
            file = getattr(ob, name)
            if file is not None and not isinstance(file, File):
                self.logger.debug("Attribute '%s' is not a File but %r",
                                  name, file)
                raise KeyError(name)
            self.attrname = name
            self.file = file
            self.state = 1
            return self
        else:
            if name in ('index_html', 'absolute_url', 'content_type'):
                return getattr(self, name)
            # extract file path in the zip
            self.filepath.append(name)
            self.state += 1
            return self

    security.declareProtected(View, 'absolute_url')
    def absolute_url(self):
        url = self.proxy.absolute_url() + '/' + KEYWORD_VIEW_ZIP
        if self.state > 0:
            url += '/' + self.attrname
        if self.state > 1:
            url += '/' + '/'.join(self.filepath)
        return url

    security.declareProtected(View, 'content_type')
    def content_type(self):
        if self.state != self.url_parts:
            return None
        return self.file.content_type

    security.declareProtected(View, 'index_html')
    def index_html(self, REQUEST, RESPONSE):
        """Publish the file or image."""
        filename = self.filepath[0]
        filepath = '/'.join(self.filepath[1:])
        key = self.absolute_url()
        last_modified = int(self.proxy.getContent().modified())
        content = zip_cache.get(key, min_date=last_modified)
        if content is None:
            self.logger.debug('extract %s from %s', filepath, filename)
            # XXX this is very ineficiant as str(file.data) load all the
            # content in memory, ofs file should implement a file-like object
            # with all stdio methods seek, tell, read, close...
            # another way will be to use a DiskFile
            zipfile = ZipFile(StringIO(str(self.file.data)), 'r')
            try:
                content = zipfile.read(filepath)
            except KeyError:
                self.logger.debug('not found %s: %s', filename, filepath)
                content = 0
            # cache for next access
            zip_cache[key] = content
        # set mime type
        registry = getToolByName(self, 'mimetypes_registry', None)
        if registry is not None:
            mimetype = registry.lookupExtension(
                os.path.basename(filepath.lower()))
            if mimetype:
                RESPONSE.setHeader('Content-Type', mimetype.normalized())
        # render content keeping original html base
        RESPONSE.setBase(None)
        return content

InitializeClass(ViewZip)

#
# Serialization
#

def unserializeProxy(ser, ob=None):
    """Unserialize a proxy from a string.

    If ob is not None, modify that object in place.
    Returns the object.
    Does not send any notification.
    """
    l = unpack('>I', ser[:4])[0]
    class_name = ser[4:4+l]
    ser = ser[4+l:]
    f = StringIO(ser)
    p = Unpickler(f)
    stuff = p.load()
    if ob is None:
        if class_name == 'ProxyFolder':
            ob = ProxyFolder('')
        elif class_name == 'ProxyDocument':
            ob = ProxyDocument('')
        elif class_name == 'ProxyFolderishDocument':
            ob = ProxyFolderishDocument('')
        else:
            logger.error('unserialize got class_name=%s', class_name)
            return None
    ob.__dict__.update(stuff)
    return ob

#
# Make Item have standard proxy methods, so that calling
# for instance ob.getContent() on a non-proxy object will work.
#

class NotAProxy:
    security = ClassSecurityInfo()

    security.declareProtected(View, 'getDocid')
    def getDocid(self):
        """No Docid."""
        return ''

    security.declareProtected(View, 'getDefaultLanguage')
    def getDefaultLanguage(self):
        """Get the default language."""
        return self.getLanguage()

    security.declareProtected(View, 'getLanguageRevisions')
    def getLanguageRevisions(self):
        """No mapping."""
        return {self.getLanguage():self.getRevision()}

    security.declareProtected(View, 'getFromLanguageRevisions')
    def getFromLanguageRevisions(self):
        """No mapping."""
        return {}

    security.declareProtected(View, 'getLanguage')
    def getLanguage(self, lang=None):
        """Get the selected language."""
        lang = 'en'
        translation_service = getToolByName(self, 'translation_service', None)
        if translation_service is not None:
            lang = translation_service.getDefaultLanguage()
        return lang

    security.declareProtected(View, 'getProxyLanguages')
    def getProxyLanguages(self):
        """return all available languages."""
        return [self.getLanguage()]

    security.declareProtected(View, 'getRevision')
    def getRevision(self, lang=None):
        """Get the best revision."""
        return 0

    security.declareProtected(View, 'getContent')
    def getContent(self, lang=None):
        """Return the object itself."""
        return self

    security.declareProtected(ModifyPortalContent, 'getEditableContent')
    def getEditableContent(self, lang=None):
        """Return the object itself."""
        return self

    security.declarePublic('isProxyArchived')
    def isProxyArchived(self):
        """Is the proxy archived."""
        return 0

    def isCPSFolderish(self):
        """Return True if the document is a structural folderish."""
        return self.isPrincipiaFolderish


InitializeClass(NotAProxy)

# Add all methods to Item class.
for attr, val in NotAProxy.__dict__.items():
    if not attr.startswith('_'):
        setattr(Item, attr, val)

#
# Concrete types for proxies.
#

factory_type_information = (
    {'id': 'CPS Proxy Folder',
     'description': 'A proxy to a folder.',
     'title': '',
     'content_icon': 'folder_icon.png',
     'product': 'CPSCore',
     'meta_type': 'CPS Proxy Folder',
     'factory': 'addProxyFolder',
     'immediate_view': '',
     'filter_content_types': 1,
     'allowed_content_types': (),
     'actions': (),
     },
    {'id': 'CPS Proxy Document',
     'description': 'A proxy to a document.',
     'title': '',
     'content_icon': 'document_icon.png',
     'product': 'CPSCore',
     'meta_type': 'CPS Proxy Document',
     'factory': 'addProxyDocument',
     'immediate_view': '',
     'filter_content_types': 1,
     'allowed_content_types': (),
     'actions': (),
     },
    {'id': 'CPS Proxy Folderish Document',
     'description': 'A proxy to a folderish document.',
     'title': '',
     'content_icon': 'folder_icon.png',
     'product': 'CPSCore',
     'meta_type': 'CPS Proxy Folderish Document',
     'factory': 'addProxyFolderishDocument',
     'immediate_view': '',
     'filter_content_types': 1,
     'allowed_content_types': (),
     'actions': (),
     },
    {'id': 'CPS Proxy BTree Folder',
     'description': 'A proxy to a folder.',
     'title': '',
     'content_icon': 'folder_icon.png',
     'product': 'CPSCore',
     'meta_type': 'CPS Proxy BTree Folder',
     'factory': 'addProxyBTreeFolder',
     'immediate_view': '',
     'filter_content_types': 1,
     'allowed_content_types': (),
     'actions': (),
     },
    {'id': 'CPS Proxy BTree Folderish Document',
     'description': 'A proxy to a folderish document.',
     'title': '',
     'content_icon': 'folder_icon.png',
     'product': 'CPSCore',
     'meta_type': 'CPS Proxy BTree Folderish Document',
     'factory': 'addProxyBTreeFolderishDocument',
     'immediate_view': '',
     'filter_content_types': 1,
     'allowed_content_types': (),
     'actions': (),
     },
    )

class ProxyFolder(ProxyBase, CPSBaseFolder):
    """A proxy folder is a folder whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy Folder'

    security = ClassSecurityInfo()

    def __init__(self, id, **kw):
        CPSBaseFolder.__init__(self, id)
        ProxyBase.__init__(self, **kw)

    def getCPSCustomCSS(self):
        """
        Return the cps custom CSS from this folder
        or from one of its parents if they have one.
        """

        portal = self.portal_url.getPortalObject()
        current = self.getContent()
        current_proxy = self

        while current.id != portal.id and \
                  getattr(current, 'cps_custom_css', "") == "":
            current_proxy = current_proxy.aq_inner.aq_parent
            current = current_proxy.getContent()

        if current.id == portal.id:
            return ""
        else:
            return current.cps_custom_css

    security.declareProtected(View, 'thisProxyFolder')
    def thisProxyFolder(self):
        """Get the closest proxy folder from a context.

        Used by acquisition.
        """
        return self

    manage_options = (CPSBaseFolder.manage_options[:1] +
                      ProxyBase.proxybase_manage_options +
                      CPSBaseFolder.manage_options[1:]
                      )

    # Changing security declarations of inherited methods from OFS.OrderSupport
    # to gain finer granularity
    security.declareProtected(ChangeSubobjectsOrder,
            'moveObjectsByDelta',
            'moveObjectsUp',
            'moveObjectsDown',
            'moveObjectsToTop',
            'moveObjectsToBottom',
            'orderObjects',
            'moveObjectToPosition',
            )

    # Trying to remain consistent with Zope default behaviour
    security.setPermissionDefault(ChangeSubobjectsOrder, ('Manager', 'Owner'))


InitializeClass(ProxyFolder)


class ProxyDocument(ProxyBase, CPSBaseDocument):
    """A proxy document is a document whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy Document'
    # portal_type will be set to the target's portal_type after creation

    def __init__(self, id, **kw):
        CPSBaseDocument.__init__(self, id)
        ProxyBase.__init__(self, **kw)

    manage_options = (ProxyBase.proxybase_manage_options +
                      CPSBaseDocument.manage_options
                      )

InitializeClass(ProxyDocument)


class ProxyFolderishDocument(ProxyFolder):
    """A proxy folderish document is a folderish document,
    whose data is indirected to a document in a repository."""

    meta_type = 'CPS Proxy Folderish Document'
    # portal_type will be set to the target's portal_type after creation

    _isFolderishDocument = 1

    security = ClassSecurityInfo()

    #
    # Utility methods
    #

    security.declareProtected(View, 'thisProxyFolderishDocument')
    def thisProxyFolderishDocument(self):
        """Return this proxy folderish document.

        Used by acquisition.
        """
        return self

    security.declareProtected(View, 'topProxyFolderishDocument')
    def topProxyFolderishDocument(self):
        """Return the top enclosing proxy folderish document.

        Used by acquisition.
        """
        container = aq_parent(aq_inner(self))
        try:
            return container.topProxyFolderishDocument()
        except AttributeError:
            return self

    security.declareProtected(View, 'thisProxyFolder')
    def thisProxyFolder(self):
        """Get the closest proxy folder from a context.

        Used by acquisition.
        """
        return self.aq_parent.thisProxyFolder()

    #
    # Freezing
    #

    security.declarePrivate('freezeProxy')
    def freezeProxy(self):
        """Freeze the proxy and all subproxies.

        (Called by CPSWorkflow.)
        """
        # XXX use an event?
        pxtool = getToolByName(self, 'portal_proxies')
        self._freezeProxyRecursive(self, pxtool)

    security.declarePrivate('_freezeProxyRecursive')
    def _freezeProxyRecursive(self, ob, pxtool):
        """Freeze this proxy and recurse."""
        if not isinstance(ob, ProxyBase):
            return
        self._freezeProxy(ob, pxtool)
        for subob in ob.objectValues():
            self._freezeProxyRecursive(subob, pxtool)

InitializeClass(ProxyFolderishDocument)


class ProxyBTreeFolder(ProxyBase, CPSBaseBTreeFolder):
    """A proxy btree folder is a folder whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy BTree Folder'

    security = ClassSecurityInfo()

    def __init__(self, id, **kw):
        CPSBaseBTreeFolder.__init__(self, id)
        ProxyBase.__init__(self, **kw)

    def __nonzero__(self):
        """Return True because proxy exists

        BTree behavior checks __len__ method, that returns True only if BTree
        is not empty ; here we only want to check that the proxy btree exists.
        """
        return True

    def getCPSCustomCSS(self):
        """
        Return the cps custom CSS from this folder
        or from one of its parents if they have one.
        """

        portal = self.portal_url.getPortalObject()
        current = self.getContent()
        current_proxy = self

        while current.id != portal.id and \
                  getattr(current, 'cps_custom_css', "") == "":
            current_proxy = current_proxy.aq_inner.aq_parent
            current = current_proxy.getContent()

        if current.id == portal.id:
            return ""
        else:
            return current.cps_custom_css

    security.declareProtected(View, 'thisProxyFolder')
    def thisProxyFolder(self):
        """Get the closest proxy folder from a context.

        Used by acquisition.
        """
        return self

    manage_options = (CPSBaseFolder.manage_options[:1] +
                      ProxyBase.proxybase_manage_options +
                      CPSBaseFolder.manage_options[1:]
                      )

InitializeClass(ProxyBTreeFolder)


class ProxyBTreeFolderishDocument(ProxyBTreeFolder):
    """A proxy btree folderish document is a folderish document,
    whose data is indirected to a document in a repository."""

    meta_type = 'CPS Proxy BTree Folderish Document'
    # portal_type will be set to the target's portal_type after creation

    _isFolderishDocument = 1

    security = ClassSecurityInfo()

    #
    # Utility methods
    #

    security.declareProtected(View, 'thisProxyFolderishDocument')
    def thisProxyFolderishDocument(self):
        """Return this proxy folderish document.

        Used by acquisition.
        """
        return self

    security.declareProtected(View, 'topProxyFolderishDocument')
    def topProxyFolderishDocument(self):
        """Return the top enclosing proxy folderish document.

        Used by acquisition.
        """
        container = aq_parent(aq_inner(self))
        try:
            return container.topProxyFolderishDocument()
        except AttributeError:
            return self

    security.declareProtected(View, 'thisProxyFolder')
    def thisProxyFolder(self):
        """Get the closest proxy folder from a context.

        Used by acquisition.
        """
        return self.aq_parent.thisProxyFolder()

    #
    # Freezing
    #

    security.declarePrivate('freezeProxy')
    def freezeProxy(self):
        """Freeze the proxy and all subproxies.

        (Called by CPSWorkflow.)
        """
        # XXX use an event?
        pxtool = getToolByName(self, 'portal_proxies')
        self._freezeProxyRecursive(self, pxtool)

    security.declarePrivate('_freezeProxyRecursive')
    def _freezeProxyRecursive(self, ob, pxtool):
        """Freeze this proxy and recurse."""
        if not isinstance(ob, ProxyBase):
            return
        self._freezeProxy(ob, pxtool)
        for subob in ob.objectValues():
            self._freezeProxyRecursive(subob, pxtool)

InitializeClass(ProxyBTreeFolderishDocument)


def addProxyFolder(container, id, REQUEST=None, **kw):
    """Add a proxy folder."""
    # container is a dispatcher when called from ZMI
    ob = ProxyFolder(id, **kw)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url() + '/manage_main')

def addProxyDocument(container, id, REQUEST=None, **kw):
    """Add a proxy document."""
    # container is a dispatcher when called from ZMI
    ob = ProxyDocument(id, **kw)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url() + '/manage_main')

def addProxyFolderishDocument(container, id, REQUEST=None, **kw):
    """Add a proxy folderish document."""
    # container is a dispatcher when called from ZMI
    ob = ProxyFolderishDocument(id, **kw)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url() + '/manage_main')

def addProxyBTreeFolder(container, id, REQUEST=None, **kw):
    """Add a proxy btree folder."""
    # container is a dispatcher when called from ZMI
    ob = ProxyBTreeFolder(id, **kw)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url() + '/manage_main')

def addProxyBTreeFolderishDocument(container, id, REQUEST=None, **kw):
    """Add a proxy btree folderish document."""
    # container is a dispatcher when called from ZMI
    ob = ProxyBTreeFolderishDocument(id, **kw)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url() + '/manage_main')

def walk_cps_folders(base):
    """Generator to walk the cps folders."""
    for o in walk(base, meta_types=(ProxyFolder.meta_type,
                                    ProxyBTreeFolder.meta_type)):
        yield o

def walk_cps_folderish(base):
    """Generator to walk the cps folders and folderish documents"""
    for o in walk(base, meta_types=(ProxyFolder.meta_type,
                                    ProxyBTreeFolder.meta_type,
                                    ProxyFolderishDocument.meta_type,
                                    ProxyBTreeFolderishDocument.meta_type)):
        yield o

def walk_cps_proxies(base):
    """Generator to walk all proxies below."""

    for o in walk(base, meta_types=(ProxyDocument.meta_type,
                                    ProxyFolder.meta_type,
                                    ProxyBTreeFolder.meta_type,
                                    ProxyFolderishDocument.meta_type,
                                    ProxyBTreeFolderishDocument.meta_type)):
        yield o

def walk_cps_except_folders(base):
    """Generator to walk all proxies below except folders.

    Useful mostly within loops already going through all folders."""

    for o in walk(base, meta_types=(ProxyDocument.meta_type,
                                    ProxyFolderishDocument.meta_type,
                                    ProxyBTreeFolderishDocument.meta_type)):
        yield o
