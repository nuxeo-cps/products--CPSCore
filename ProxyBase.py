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

from zLOG import LOG, ERROR, DEBUG
from ExtensionClass import Base
from cPickle import Pickler, Unpickler
from cStringIO import StringIO
from struct import pack, unpack
from ComputedAttribute import ComputedAttribute
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo
from Acquisition import aq_base, aq_parent, aq_inner

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import AccessContentsInformation
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

from Products.NuxCPS3.EventServiceTool import getEventService
from Products.NuxCPS3.CPSBase import CPSBaseFolder
from Products.NuxCPS3.CPSBase import CPSBaseDocument


class ProxyBase(Base):
    """Mixin class for proxy types.

    A proxy stores the repoid of the document family it points to,
    and a mapping of language -> version.
    """

    security = ClassSecurityInfo()

    def __init__(self, repoid, version_infos):
        self._repoid = repoid
        self._version_infos = version_infos

    #
    # API
    #

    security.declarePrivate('setVersionInfos')
    def setVersionInfos(self, version_infos):
        """Set the version infos for this proxy.

        The version infos is a dict of language -> version,
        where language can be '*' for the default, and version
        is an integer.
        """
        self._version_infos = version_infos.copy()
        # XXX notify event service of change ?
        # XXX this method is not called yet (will be with i18n)

    security.declareProtected(View, 'getVersionInfos')
    def getVersionInfos(self):
        """Return the version infos for this proxy."""
        return self._version_infos.copy()

    security.declareProtected(View, 'getRepoId')
    def getRepoId(self):
        """Return the repoid for this proxy."""
        return self._repoid

    # XXX permission ?
    security.declareProtected(AccessContentsInformation, 'getContent')
    def getContent(self, lang=None):
        """Return the content object referred to by this proxy.

        The returned object may depend on the current language.
        """
        return self._getContent(lang=lang)

    security.declareProtected(View, 'getVersion')
    def getVersion(self, lang=None):
        """Return the version of this proxy in the current language."""
        if lang is None:
            lang = '*' # XXX
        version_infos = self._version_infos
        if version_infos.has_key(lang):
            version_info = version_infos[lang]
        elif version_infos.has_key('*'):
            version_info = version_infos['*']
        else:
            version_info = 0
        return version_info

    security.declareProtected(ModifyPortalContent, 'getEditableContent')
    def getEditableContent(self, lang=None):
        """Return the editable content object referred to by this proxy.

        The returned object may depend on the current language.
        """
        return self._getContent(lang=lang, editable=1)

    def _getContent(self, lang=None, editable=0):
        """Get the content object, maybe editable."""
        pxtool = getToolByName(self, 'portal_proxies', None)
        if pxtool is None:
            LOG('ProxyBase', ERROR, 'No portal_proxies found')
            return None
        hubtool = getToolByName(self, 'portal_eventservice', None)
        if hubtool is None:
            LOG('ProxyBase', ERROR, 'No portal_eventservice found')
            return None
        hubid = hubtool.getHubId(self)
        if hubid is None:
            LOG('ProxyBase', DEBUG, 'No hubid found for proxy object %s'
                % '/'.join(self.getPhysicalPath()))
            return None
        ob, lang, version_info = pxtool.getContent(hubid, lang=lang, editable=editable)
        if editable and version_info is not None:
            if version_info != self.getVersion(lang=lang):
                # Update proxy if version has changed because editable.
                self._p_changed = 1
                self._version_infos[lang] = version_info
                # Notify of this change.
                evtool = getEventService(self)
                evtool.notify('sys_modify_object', self, {})
        return ob

    security.declarePrivate('freezeProxy')
    def freezeProxy(self):
        """Freeze the proxy.

        (Called by CPSWorkflow.)
        """
        hubtool = getToolByName(self, 'portal_eventservice')
        pxtool = getToolByName(self, 'portal_proxies')
        self._freezeProxy(self, hubtool, pxtool)

    security.declarePrivate('_freezeProxy')
    def _freezeProxy(self, ob, hubtool, pxtool):
        """Freeze the proxy."""
        # XXX use an event?
        hubid = hubtool.getHubId(ob)
        if hubid is not None:
            pxtool.freezeProxy(hubid)

    def __getattr__(self, name):
        """Transparent traversal of the proxy to the real subobjects."""
        ob = self._getContent()
        if ob is None:
            raise AttributeError, name
        res = getattr(ob, name) # may raise AttributeError
        if hasattr(res, '__of__'):
            # XXX Maybe incorrect if complex wrapping.
            res = aq_base(res).__of__(self)
        return res

##     def __getitem__(self, name):
##         """Transparent traversal of the proxy to the real subobjects."""
##         if hasattr(self, name):
##             raise KeyError, name
##         ob = self._getContent()
##         if ob is None:
##             raise KeyError, name
##         if hasattr(ob, name):
##             return getattr(ob, name)
##         try:
##             return ob[name]
##         except (KeyError, IndexError, TypeError, AttributeError):
##             raise KeyError, name

    #
    # Staging
    #

    security.declarePrivate('serialize_proxy')
    def serialize_proxy(self):
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
                 '_repoid',
                 '_version_infos',
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
            LOG('Proxybase', DEBUG, 'serialize of %s found unknown %s=%s'
                % (self.getId(), k, v))
        # now serialize stuff
        f = StringIO()
        p = Pickler(f, 1)
        p.dump(stuff)
        ser = f.getvalue()
        class_name = self.__class__.__name__
        return (pack('>I', len(class_name))
                +class_name
                +ser)

    security.declarePublic('test_serialize') # XXX tests
    def test_serialize(self):
        """Test serialization."""
        ser = self.serialize_proxy()
        ob = unserialize_proxy(ser)
        return `ob.__dict__`

    #
    # Security
    #

    def _setSecurity(self):
        """Propagate security changes made on the proxy."""
        # Now gather permissions for each version
        pxtool = getToolByName(self, 'portal_proxies')
        pxtool.setSecurity(self)

    def _setSecurityRecursive(self, ob, pxtool=None):
        """Propagate security changes made on the proxy."""
        try:
            isproxy = isinstance(ob, ProxyBase)
        except TypeError:
            # In python 2.1 isinstance() raises TypeError
            # instead of returning 0 for ExtensionClasses.
            isproxy = 0
        if not isproxy:
            return
        if pxtool is None:
            pxtool = getToolByName(self, 'portal_proxies')
        pxtool.setSecurity(ob)
        for subob in ob.objectValues():
            self._setSecurityRecursive(subob, pxtool=pxtool)

    # overloaded
    def reindexObject(self, idxs=[]):
        """Called to reindex when the object has changed."""
        LOG('ProxyBase', DEBUG, 'reindex idxs=%s for %s' % (idxs, '/'.join(self.getPhysicalPath())))
        if not idxs or 'allowedRolesAndUsers' in idxs:
            # XXX should use an event for that
            self._setSecurity()
        # Doesn't work if CMFCatalogAware isn't an ExtensionClass:
        #return CMFCatalogAware.reindexObject(self, idxs=idxs)
        return CMFCatalogAware.__dict__['reindexObject'](self, idxs=idxs)

    # overloaded
    def reindexObjectSecurity(self):
        """Called to security-related indexes."""
        LOG('ProxyBase', DEBUG, 'reindex security for %s' % '/'.join(self.getPhysicalPath()))
        # XXX should use an event for that
        self._setSecurityRecursive(self)
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
        {'id':'RepoId', 'type':'string', 'mode':''},
        {'id':'VersionInfos', 'type':'string', 'mode':''},
        )
    RepoId = ComputedAttribute(getRepoId, 1)
    VersionInfos = ComputedAttribute(getVersionInfos, 1)

InitializeClass(ProxyBase)

#
# Serialization
#

def unserialize_proxy(ser, ob=None):
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


factory_type_information = (
    {'id': 'CPS Proxy Folder',
     'description': 'A proxy to a folder.',
     'title': '',
     'content_icon': 'folder_icon.gif',
     'product': 'NuxCPS3',
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
     'content_icon': 'document_icon.gif',
     'product': 'NuxCPS3',
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
     'content_icon': 'folder_icon.gif',
     'product': 'NuxCPS3',
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
    # portal_type will be set to the target's portal_type after creation

    def __init__(self, id, repoid=None, version_infos=None):
        CPSBaseFolder.__init__(self, id)
        ProxyBase.__init__(self, repoid, version_infos)

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

    def __init__(self, id, repoid=None, version_infos=None):
        CPSBaseDocument.__init__(self, id)
        ProxyBase.__init__(self, repoid, version_infos)

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
        hubtool = getToolByName(self, 'portal_eventservice')
        pxtool = getToolByName(self, 'portal_proxies')
        self._freezeProxyRecursive(self, hubtool, pxtool)

    security.declarePrivate('_freezeProxyRecursive')
    def _freezeProxyRecursive(self, ob, hubtool, pxtool):
        """Freeze this proxy and recurse."""
        try:
            isproxy = isinstance(ob, ProxyBase)
        except TypeError:
            # In python 2.1 isinstance() raises TypeError
            # instead of returning 0 for ExtensionClasses.
            isproxy = 0
        if not isproxy:
            return
        self._freezeProxy(ob, hubtool, pxtool)
        for subob in ob.objectValues():
            self._freezeProxyRecursive(subob, hubtool, pxtool)

InitializeClass(ProxyFolderishDocument)


def addProxyFolder(container, id, repoid=None, version_infos=None,
                   REQUEST=None):
    """Add a proxy folder."""
    # container is a dispatcher when called from ZMI
    ob = ProxyFolder(id, repoid=repoid, version_infos=version_infos)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')

def addProxyDocument(container, id, repoid=None, version_infos=None,
                     REQUEST=None):
    """Add a proxy document."""
    # container is a dispatcher when called from ZMI
    ob = ProxyDocument(id, repoid=repoid, version_infos=version_infos)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')

def addProxyFolderishDocument(container, id, repoid=None, version_infos=None,
                              REQUEST=None):
    """Add a proxy folderish document."""
    # container is a dispatcher when called from ZMI
    ob = ProxyFolderishDocument(id, repoid=repoid, version_infos=version_infos)
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')
