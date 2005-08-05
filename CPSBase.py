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
"""Base types used to construct most CPS content.
"""

import sys
import warnings
from types import StringType, UnicodeType

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import manage_properties, access_contents_information
from Acquisition import aq_parent, aq_inner

from OFS.ObjectManager import ObjectManager
from OFS.PropertyManager import PropertyManager
from OFS.FindSupport import FindSupport
from zLOG import LOG, ERROR

from Products.CMFCore.permissions import View
from Products.CMFCore.permissions import ModifyPortalContent
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware
from Products.CMFCore.PortalFolder import PortalFolder
from Products.CMFCore.PortalContent import PortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl
try:
    from Products.CMFCore.CMFBTreeFolder import CMFBTreeFolder
except ImportError:
    from Products.BTreeFolder2.CMFBTreeFolder import CMFBTreeFolder

from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.CPSTypes import TypeConstructor, TypeContainer


defaultencoding = sys.getdefaultencoding()


class CPSBaseDocument(CMFCatalogAware, PortalFolder, PortalContent,
                      DefaultDublinCoreImpl, PropertyManager):
    """The base from which all CPS content objects derive."""

    meta_type = 'CPS Base Document'
    portal_type = None

    #_isDiscussable = 1
    isPrincipiaFolderish = 0
    __dav_collection__ = 0
    isAnObjectManager = 0

    security = ClassSecurityInfo()

    _properties = (
        {'id':'title', 'type':'string', 'mode':'w', 'label':'Title'},
        {'id':'description', 'type':'text', 'mode':'w', 'label':'Description'},
        )
    title = ''
    description = ''

    def __init__(self, id, **kw):
        self.id = id
        dckw = {}
        for p in ('title', 'subject', 'description', 'contributors',
                  'effective_date', 'expiration_date', 'format',
                  'language', 'rights'):
            if kw.has_key(p):
                dckw[p] = kw[p]
        DefaultDublinCoreImpl.__init__(self, **dckw)

    security.declareProtected(ModifyPortalContent, 'setTitle')
    # def setTitle() needs a better permission than PortalFolder's

    def _checkId(self, id, allow_dup=0):
        PortalFolder.inheritedAttribute('_checkId')(self, id, allow_dup)

        # This method prevents people other than the portal manager
        # from overriding skinned names.
        if not allow_dup:
            if not _checkPermission( 'Manage portal', self):
                ob = self
                while ob is not None and not getattr(ob, '_isPortalRoot', 0):
                    ob = aq_parent(aq_inner(ob))
                if ob is not None:
                    # If the portal root has an object by this name,
                    # don't allow an override.
                    # FIXME: needed to allow index_html for join code
                    if (hasattr(ob, id) and
                        id != 'index_html' and
                        not id.startswith('.')):
                        raise 'Bad Request', (
                            'The id "%s" is reserved.' % id)
                    # Otherwise we're ok.

    security.declareProtected(ModifyPortalContent, 'edit')
    def edit(self, **kw):
        """Edit the document."""
        self.manage_changeProperties(**kw)
        self.reindexObject()
        evtool = getEventService(self)
        # Note: usually we're not a proxy. The repository will listen
        # for this event and propagate it to the relevant proxies.
        evtool.notify('sys_modify_object', self, {})

    security.declareProtected(View, 'SearchableText')
    def SearchableText(self):
        """The searchable text for this object.

        Automatically derived from all string properties.
        """
        try:
            values = self.propertyValues()
        except AttributeError, err:
            LOG('CPSBase.SearchableText', ERROR,
                'unable to get propertyValues for obj %s, '
                'AttributeError on %s' % (self.absolute_url(1), err))
            values = []
        strings = []
        for val in values:
            if isinstance(val, StringType) or isinstance(val, UnicodeType):
                strings.append(val)

        try:
            res = ' '.join(strings)
        except UnicodeError:
            ustrings = []
            for s in strings:
                if isinstance(s, UnicodeType):
                    ustrings.append(s)
                else:
                    ustrings.append(unicode(s, defaultencoding, 'ignore'))
            res = ' '.join(ustrings)
        return res

    #
    # ZMI
    #

    manage_options = (
        PropertyManager.manage_options[:1] + # Properties
        ObjectManager.manage_options[:1] + # Contents
        PortalContent.manage_options + # DublinCore, Edit, View, Owner, Secu
        FindSupport.manage_options # Find
        )

InitializeClass(CPSBaseDocument)


class CPSBaseFolder(TypeConstructor, TypeContainer, CPSBaseDocument):
    """The base from which all CPS folder objects derive."""

    meta_type = 'CPS Base Folder'

    isPrincipiaFolderish = 1
    __dav_collection__ = 1
    isAnObjectManager = 1
    security = ClassSecurityInfo()

    #
    # ZMI
    #

    manage_options = (
        ObjectManager.manage_options[:1] + # Contents
        PropertyManager.manage_options[:1] + # Properties
        PortalContent.manage_options + # DublinCore, Edit, View, Owner, Secu
        FindSupport.manage_options # Find
        )

    # BBB old orderedfolder method names:
    security.declareProtected(manage_properties, 'move_object_up')
    def move_object_up(self, ids, delta=1, subset_ids=None):
        """ Move specified sub-objects up by delta in container.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"move_object_up" is now called "moveObjectsUp"',
                      DeprecationWarning)
        return self.moveObjectsUp(ids, delta, subset_ids)

    security.declareProtected(manage_properties, 'move_object_down')
    def move_object_down(self, ids, delta=1, subset_ids=None):
        """ Move specified sub-objects down by delta in container.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"move_object_down" is now called "moveObjectsDown"',
                      DeprecationWarning)
        return self.moveObjectsDown(ids, delta, subset_ids)

    security.declareProtected(manage_properties, 'move_object_to_top')
    def move_object_to_top(self, ids, subset_ids=None):
        """ Move specified sub-objects to top of container.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"move_object_to_top" is now called "moveObjectsToTop"',
                      DeprecationWarning)
        return self.moveObjectsToTop(ids, subset_ids )

    security.declareProtected(manage_properties, 'move_object_to_bottom')
    def move_object_to_bottom(self, ids, subset_ids=None):
        """ Move specified sub-objects to bottom of container.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"move_object_to_bottom" is now called "moveObjectsToBottom"',
                      DeprecationWarning)
        return self.moveObjectsToBottom(ids, subset_ids)

    security.declareProtected(access_contents_information,
                              'get_object_position')
    def get_object_position(self, id):
        """ Get the position of an object by its id.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"get_object_position" is now called "getObjectPosition"',
                      DeprecationWarning)
        return self.getObjectPosition(id)

    security.declareProtected(manage_properties, 'move_object_to_position')
    def move_object_to_position(self, id, position):
        """ Move specified object to absolute position.
        """
        warnings.warn('The naming of OrderSupport methods have changed. '
                      '"move_object_to_position" is now called "moveObjectToPosition"',
                      DeprecationWarning)
        self.moveObjectToPosition(id, position)


InitializeClass(CPSBaseFolder)


class CPSBaseBTreeDocument(CMFCatalogAware, CMFBTreeFolder, PortalContent,
                           DefaultDublinCoreImpl, PropertyManager):
    """The base container document which is based on BTree."""

    meta_type = 'CPS Base BTree Document'
    portal_type = None

    #_isDiscussable = 1
    isPrincipiaFolderish = 0
    __dav_collection__ = 0
    isAnObjectManager = 0

    security = ClassSecurityInfo()

    _properties = (
        {'id':'title', 'type':'string', 'mode':'w', 'label':'Title'},
        {'id':'description', 'type':'text', 'mode':'w', 'label':'Description'},
        )
    title = ''
    description = ''

    def __init__(self, id, **kw):
        self.id = id
        dckw = {}
        for p in ('title', 'subject', 'description', 'contributors',
                  'effective_date', 'expiration_date', 'format',
                  'language', 'rights'):
            if kw.has_key(p):
                dckw[p] = kw[p]

        CMFBTreeFolder.__init__(self, id)
        DefaultDublinCoreImpl.__init__(self, **dckw)

    security.declareProtected(ModifyPortalContent, 'setTitle')
    # def setTitle() needs a better permission than PortalFolder's

    def _checkId(self, id, allow_dup=0):
        CMFBTreeFolder.inheritedAttribute('_checkId')(self, id, allow_dup)

        # This method prevents people other than the portal manager
        # from overriding skinned names.
        if not allow_dup:
            if not _checkPermission( 'Manage portal', self):
                ob = self
                while ob is not None and not getattr(ob, '_isPortalRoot', 0):
                    ob = aq_parent(aq_inner(ob))
                if ob is not None:
                    # If the portal root has an object by this name,
                    # don't allow an override.
                    # FIXME: needed to allow index_html for join code
                    if (hasattr(ob, id) and
                        id != 'index_html' and
                        not id.startswith('.')):
                        raise 'Bad Request', (
                            'The id "%s" is reserved.' % id)
                    # Otherwise we're ok.

    security.declareProtected(ModifyPortalContent, 'edit')
    def edit(self, **kw):
        """Edit the document."""
        self.manage_changeProperties(**kw)
        self.reindexObject()
        evtool = getEventService(self)
        # Note: usually we're not a proxy. The repository will listen
        # for this event and propagate it to the relevant proxies.
        evtool.notify('sys_modify_object', self, {})

    security.declareProtected(View, 'SearchableText')
    def SearchableText(self):
        """The searchable text for this object.

        Automatically derived from all string properties.
        """
        try:
            values = self.propertyValues()
        except AttributeError, err:
            LOG('CPSBase.SearchableText', ERROR,
                'unable to get propertyValues for obj %s, '
                'AttributeError on %s' % (self.absolute_url(1), err))
            values = []
        strings = []
        for val in values:
            if isinstance(val, StringType) or isinstance(val, UnicodeType):
                strings.append(val)

        try:
            res = ' '.join(strings)
        except UnicodeError:
            ustrings = []
            for s in strings:
                if isinstance(s, UnicodeType):
                    ustrings.append(s)
                else:
                    ustrings.append(unicode(s, defaultencoding, 'ignore'))
            res = ' '.join(ustrings)
        return res

    #
    # ZMI
    #

    manage_options = (
        PropertyManager.manage_options[:1] + # Properties
        ObjectManager.manage_options[:1] + # Contents
        PortalContent.manage_options + # DublinCore, Edit, View, Owner, Secu
        FindSupport.manage_options # Find
        )

InitializeClass(CPSBaseBTreeDocument)


class CPSBaseBTreeFolder(TypeConstructor, TypeContainer, CPSBaseBTreeDocument):
    """The base folder which is based on BTree."""

    meta_type = 'CPS Base BTree Folder'

    isPrincipiaFolderish = 1
    __dav_collection__ = 1
    isAnObjectManager = 1

    #
    # ZMI
    #

    manage_options = (
        ObjectManager.manage_options[:1] + # Contents
        PropertyManager.manage_options[:1] + # Properties
        PortalContent.manage_options + # DublinCore, Edit, View, Owner, Secu
        FindSupport.manage_options # Find
        )

InitializeClass(CPSBaseBTreeFolder)


def CPSBase_adder(container, object, REQUEST=None):
    """Adds a just constructed object to its container."""
    # When called from the ZMI, container is a dispatcher.
    id = object.getId()
    container._setObject(id, object)
    if REQUEST is not None:
        url = container.absolute_url()
        REQUEST.RESPONSE.redirect('%s/manage_main' % url)
