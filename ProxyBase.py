# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
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

import os.path
from zLOG import LOG, ERROR, DEBUG, TRACE
from ExtensionClass import Base
from cPickle import Pickler, Unpickler
from cStringIO import StringIO
import os
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
from OFS.Image import File
from webdav.WriteLockInterface import WriteLockInterface

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

from Products.CPSCore.utils import _isinstance
from Products.CPSCore.utils import isUserAgentMsie

from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.CPSBase import CPSBaseFolder
from Products.CPSCore.CPSBase import CPSBaseDocument


KEYWORD_DOWNLOAD_FILE = 'downloadFile'
KEYWORD_ARCHIVED_REVISION = 'archivedRevision'
KEYWORD_ARCHIVED_LANGUAGE = 'switchLanguage'
PROBLEMATIC_FILES_SUFFIXES = ('.exe', '.sxw', '.sxc')


class ProxyBase(Base):
    """Mixin class for proxy types.

    A proxy stores:

    - docid, the document family it points to.

    - language_revs, a mapping of language -> revision. The revision is
      an integer representing a single revision of a document.

    - tag, an optional integer tag. A tag is an abstract reference to
      the mapping language -> revision. It is used to provide branch
      lineage between proxies. """

    security = ClassSecurityInfo()

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

    security.declareProtected(View, 'getDefaultLanguage')
    def getDefaultLanguage(self):
        """Get the default language for this proxy."""
        return self._default_language

    security.declarePrivate('setDefaultLanguage')
    def setDefaultLanguage(self, default_language):
        """Set the default language for this proxy.

        (Called by ProxyTool.)
        """
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

    security.declareProtected(View, 'getLanguage')
    def getLanguage(self, lang=None):
        """Get the selected language for a proxy."""
        pxtool = getToolByName(self, 'portal_proxies')
        return pxtool.getBestRevision(self, lang=lang)[0]

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
        """Get the content object, maybe editable."""
        pxtool = getToolByName(self, 'portal_proxies')
        return pxtool.getContent(self, lang=lang, rev=rev, editable=editable)

    security.declarePrivate('proxyChanged')
    def proxyChanged(self):
        """Do necessary notifications after a proxy was changed."""
        pxtool = getToolByName(self, 'portal_proxies')
        utool = getToolByName(self, 'portal_url')
        rpath = utool.getRelativeUrl(self)
        pxtool._modifyProxy(self, rpath) # XXX or directly event ?
        pxtool.setSecurity(self)
        evtool = getEventService(self)
        evtool.notify('sys_modify_object', self, {})

    def __getitem__(self, name):
        """Transparent traversal of the proxy to the real subobjects.

        Used for skins that don't take proxies enough into account.

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
        elif name == KEYWORD_ARCHIVED_LANGUAGE:
            if self.isProxyArchived():
                raise KeyError(name)
            switcher = LanguageSwitcher(self)
            return switcher.__of__(self)
        ob = self._getContent()
        if ob is None:
            raise KeyError(name)
        if name == KEYWORD_DOWNLOAD_FILE:
            downloader = FileDownloader(ob, self)
            return downloader.__of__(self)
        try:
            res = getattr(ob, name)
        except AttributeError:
            try:
                res = ob[name]
            except (KeyError, IndexError, TypeError, AttributeError):
                raise KeyError, name
        if hasattr(res, '__of__'):
            # XXX Maybe incorrect if complex wrapping.
            res = aq_base(res).__of__(self)
        return res

    #
    # Freezing
    #

    security.declarePrivate('freezeProxy')
    def freezeProxy(self):
        """Freeze the proxy.

        Freezing means that any attempt at modification will create a new
        revision. This allows for lazy copying.

        (Called by CPSWorkflow.)
        """
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
            LOG('ProxyBase', DEBUG,
                "Warning: serialize of %s found unknown %s=%s"
                % (self.getId(), k, v))
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

    # FIXME: this should go to a unit test
    security.declarePublic('test_serialize') # XXX tests
    def test_serialize(self):
        """Test serialization."""
        ser = self.serializeProxy()
        ob = unserializeProxy(ser)
        return `ob.__dict__`

    #
    # Security
    #

    def _setSecurity(self):
        """Propagate security changes made on the proxy."""
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool.setSecurity(self)

    def _setSecurityRecursive(self, ob, pxtool=None):
        """Propagate security changes made on the proxy."""
        if not _isinstance(ob, ProxyBase):
            return
        if pxtool is None:
            pxtool = getToolByName(self, 'portal_proxies')
        pxtool.setSecurity(ob)
        for subob in ob.objectValues():
            self._setSecurityRecursive(subob, pxtool=pxtool)

    # overloaded
    def reindexObject(self, idxs=[]):
        """Called to reindex when the object has changed."""
        LOG('ProxyBase', DEBUG, "reindex idxs=%s for %s"
            % (idxs, '/'.join(self.getPhysicalPath())))
        if not idxs or 'allowedRolesAndUsers' in idxs:
            # XXX should use an event for that
            self._setSecurity()
        if 'allowedRolesAndUsers' in idxs:
            # Both must be updated
            idxs.append('localUsersWithRoles')
        # Doesn't work if CMFCatalogAware isn't an ExtensionClass:
        #return CMFCatalogAware.reindexObject(self, idxs=idxs)
        return CMFCatalogAware.__dict__['reindexObject'](self, idxs=idxs)

    # overloaded
    def reindexObjectSecurity(self):
        """Called to security-related indexes."""
        LOG('ProxyBase', DEBUG, "reindex security for %s"
            % '/'.join(self.getPhysicalPath()))
        # XXX should use an event for that
        self._setSecurityRecursive(self)
        # Notify that this proxy's security has changed.
        # Listeners will have to recurse if necessary.
        # (The notification for the object repo is done by the repo.)
        evtool = getEventService(self)
        evtool.notify('sys_modify_security', self, {})
        return CMFCatalogAware.__dict__['reindexObjectSecurity'](self)

    # XXX also call _setSecurity from:
    #  manage_role
    #  manage_acquiredPermissions
    #  manage_changePermissions

    #
    # Helpers
    #

    security.declarePublic('Title')
    def Title(self):
        """The object's title."""
        ob = self.getContent()
        if ob is not None:
            return ob.Title()
        else:
            return ''

    security.declarePublic('title_or_id')
    def title_or_id(self):
        """The object's title or id."""
        return self.Title() or self.getId()

    security.declarePublic('SearchableText')
    def SearchableText(self):
        """No searchable text."""
        return ''

    security.declarePublic('Type')
    def Type(self):
        """Dublin core Type."""
        # Used by main_template.
        ob = self.getContent()
        if ob is not None:
            return ob.Type()
        else:
            return ''

    security.declarePublic('Languages')
    def Languages(self):
        """return all available languages."""
        return self.getLanguageRevisions().keys()

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


class FileDownloader(Acquisition.Explicit):
    """Intermediate object allowing for file download.

    Returned by a proxy during traversal of .../downloadFile/.

    Parses URLs of the form .../downloadFile/attrname/mydocname.pdf
    """

    __implements__ = (WriteLockInterface,)

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    def __init__(self, ob, proxy):
        """
        Init the FileDownloader with the document and proxy to which it pertains.

        ob is the document that owns the file and proxy is the proxy of this
        same document
        """
        self.ob = ob
        self.proxy = proxy
        self.state = 0
        self.attrname = None
        self.file = None
        self.filename = None

    def __repr__(self):
        s = '<FileDownloader for %s' % `self.ob`
        if self.state > 0:
            s += '/'+self.attrname
        if self.state > 1:
            s += '/'+self.filename
        s += '>'
        return s

    def __bobo_traverse__(self, request, name):
        state = self.state
        ob = self.ob
        LOG('FileDownloader.getitem', DEBUG, "state=%s name=%s"
            % (state, name))
        if state == 0:
            # First call, swallow attribute
            if not hasattr(aq_base(ob), name):
                LOG('FileDownloader.getitem', DEBUG,
                    "Not a base attribute: '%s'" % name)
                raise KeyError(name)
            file = getattr(ob, name)
            if file is not None and not _isinstance(file, File):
                LOG('FileDownloader.getitem', DEBUG,
                    "Attribute '%s' is not a File but %s" %
                    (name, `file`))
                raise KeyError(name)
            self.attrname = name
            self.file = file
            self.state = 1
            return self
        elif state == 1:
            # Got attribute, swallow filename
            self.filename = name
            self.state = 2
            self.meta_type = getattr(self.file, 'meta_type', '')
            return self
        elif name in ('index_html', 'absolute_url', 'content_type',
                      'HEAD', 'PUT', 'LOCK', 'UNLOCK',):
            return getattr(self, name)
        else:
            raise KeyError(name)

    security.declareProtected(View, 'absolute_url')
    def absolute_url(self):
        url = self.proxy.absolute_url() + '/' + KEYWORD_DOWNLOAD_FILE
        if self.state > 0:
            url += '/' + self.attrname
        if self.state > 1:
            url += '/' + self.filename
        return url

    security.declareProtected(View, 'content_type')
    def content_type(self):
        if self.state != 2:
            return None
        return self.file.content_type

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

    security.declareProtected(View, 'HEAD')
    def HEAD(self, REQUEST, RESPONSE):
        """Retrieve the HEAD information for HTTP."""
        if self.state != 2:
            return None
        file = self.file
        if file is not None:
            return file.HEAD(REQUEST, RESPONSE)
        else:
            RESPONSE.setHeader('Content-Type', 'text/plain')
            RESPONSE.setHeader('Content-Length', '0')
            return ''

    security.declareProtected(ModifyPortalContent, 'PUT')
    def PUT(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) PUT requests (WebDAV)."""
        LOG('FileDownloader', DEBUG, "PUT()")
        if self.state != 2:
            LOG('ProxyBase', DEBUG, "BadRequest: Cannot PUT with state != 2")
            raise 'BadRequest', "Cannot PUT with state != 2"
        document = self.proxy.getEditableContent()
        file = getattr(document, self.attrname)
        response = file.PUT(REQUEST, RESPONSE)
        # If the considered document is a CPSDocument we must use the edit()
        # method since this method does important things such as setting dirty
        # flags on modified fields.
        # XXX: Note that using edit() modifies the file attribute twice.
        # We shouldn't use the file.PUT() method but it is helpful to get the
        # needed response object.
        if getattr(aq_base(document), '_has_generic_edit_method', 0):
            document.edit({self.attrname: file})
        return response

    security.declareProtected(ModifyPortalContent, 'LOCK')
    def LOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) LOCK requests (WebDAV)."""
        LOG('FileDownloader', DEBUG, "LOCK()")
        if self.state != 2:
            LOG('ProxyBase', DEBUG, "BadRequest: Cannot LOCK with state != 2")
            raise 'BadRequest', "Cannot LOCK with state != 2"
        document = self.proxy.getEditableContent()
        file = getattr(document, self.attrname)
        return file.LOCK(REQUEST, RESPONSE)

    security.declareProtected(ModifyPortalContent, 'UNLOCK')
    def UNLOCK(self, REQUEST, RESPONSE):
        """Handle HTTP (and presumably FTP?) UNLOCK requests (WebDAV)."""
        LOG('FileDownloader', DEBUG, "UNLOCK()")
        if self.state != 2:
            LOG('ProxyBase', DEBUG, "BadRequest: Cannot UNLOCK with state != 2")
            raise 'BadRequest', "Cannot UNLOCK with state != 2"
        document = self.proxy.getEditableContent()
        file = getattr(document, self.attrname)
        return file.UNLOCK(REQUEST, RESPONSE)

    def wl_lockValues(self, killinvalids=0):
        """Handle HTTP (and presumably FTP?) wl_lockValues requests (WebDAV)."""
        LOG('FileDownloader', DEBUG, "wl_lockValues()")
        if self.state != 2:
            LOG('ProxyBase', DEBUG, "BadRequest: Cannot wl_lockValues with state != 2")
            raise 'BadRequest', "Cannot wl_lockValues with state != 2"
        document = self.proxy.getEditableContent()
        file = getattr(document, self.attrname)
        return file.wl_lockValues(killinvalids)

    def wl_isLocked(self):
        """Handle HTTP (and presumably FTP?) wl_isLocked requests (WebDAV)."""
        LOG('FileDownloader', DEBUG, "wl_isLocked()")
        if self.state != 2:
            LOG('ProxyBase', DEBUG, "BadRequest: Cannot wl_isLocked with state != 2")
            raise 'BadRequest', "Cannot wl_isLocked with state != 2"
        document = self.proxy.getEditableContent()
        file = getattr(document, self.attrname)
        return file.wl_isLocked()

InitializeClass(FileDownloader)


class LanguageSwitcher(Acquisition.Explicit):
    """Language Switcher."""

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    # Never viewable, so skipped by breadcrumbs.
    _View_Permission = ()

    def __init__(self, proxy):
        self.proxy = proxy
        self.id = KEYWORD_ARCHIVED_LANGUAGE

    def __repr__(self):
        return '<LanguageSwitcher for %s>' % repr(self.proxy)

    def __bobo_traverse__(self, REQUEST, lang):
        proxy = self.proxy
        utool = getToolByName(self, 'portal_url')
        rpath = utool.getRelativeUrl(proxy)
        # store information by the time of the request to change the
        # language used for viewing the current document, bypassing Localizer.
        # XXX Use rpath in the key not to propagate the change to other
        # documents viewed. Append the keyword to it not to make a too generic
        # key.
        REQUEST._cps_switch_language = (rpath, lang)
        #  Return the proxy, and so have the same context than without language
        #  switcher.
        return proxy

InitializeClass(LanguageSwitcher)


class RevisionSwitcher(Acquisition.Explicit):
    """Intermediate object allowing for revision choice.

    Returned by a proxy during traversal of .../archivedRevision/.

    Parses URLs of the form .../archivedRevision/n/...
    """

    security = ClassSecurityInfo()
    security.declareObjectPublic()

    # Never viewable, so skipped by breadcrumbs.
    _View_Permission = ()

    def __init__(self, proxy):
        self.proxy = proxy
        self.id = KEYWORD_ARCHIVED_REVISION

    def __repr__(self):
        return '<RevisionSwitcher for %s>' % `self.proxy`

    def __bobo_traverse__(self, request, rev):
        try:
            rev = int(rev)
        except ValueError:
            LOG('RevisionSwitcher.getitem', DEBUG,
                "Invalid revision %s" % `rev`)
            raise KeyError(rev)

        proxy = self.proxy
        docid = proxy._docid
        pxtool = getToolByName(proxy, 'portal_proxies')
        ob = pxtool.getContentByRevision(docid, rev)
        if ob is None:
            LOG('RevisionSwitcher.getitem', DEBUG,
                "Unknown revision %s" % rev)
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
    security.declareObjectPublic()

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
        return self._ob

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
            LOG('ProxyBase', ERROR, 'unserialize got class_name=%s' %
                class_name)
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
        return 'en'

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
        # XXX TODO Translation Service should be used in the near future
        Localizer = getToolByName(self, 'Localizer', None)
        lang = 'en'
        if Localizer is not None:
            # use the portal default language
            lang = Localizer.get_default_language()
        return lang

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
    )

class ProxyFolder(ProxyBase, CPSBaseFolder):
    """A proxy folder is a folder whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy Folder'

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

    manage_options = (CPSBaseFolder.manage_options[:1] +
                      ProxyBase.proxybase_manage_options +
                      CPSBaseFolder.manage_options[1:]
                      )

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
        if not _isinstance(ob, ProxyBase):
            return
        self._freezeProxy(ob, pxtool)
        for subob in ob.objectValues():
            self._freezeProxyRecursive(subob, pxtool)

InitializeClass(ProxyFolderishDocument)


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
