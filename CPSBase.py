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
from types import StringType, UnicodeType

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Acquisition import aq_parent, aq_inner, aq_base

from OFS.ObjectManager import ObjectManager
from OFS.PropertyManager import PropertyManager
from OFS.FindSupport import FindSupport
from zLOG import LOG, ERROR

from Products.CMFCore.CMFCorePermissions import View
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware
from Products.CMFCore.PortalFolder import PortalFolder
from Products.CMFCore.PortalContent import PortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl

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

    #
    # ZMI
    #

    manage_options = (
        ObjectManager.manage_options[:1] + # Contents
        PropertyManager.manage_options[:1] + # Properties
        PortalContent.manage_options + # DublinCore, Edit, View, Owner, Secu
        FindSupport.manage_options # Find
        )

InitializeClass(CPSBaseFolder)


def CPSBase_adder(container, object, REQUEST=None):
    """Adds a just constructed object to its container."""
    # When called from the ZMI, container is a dispatcher.
    id = object.getId()
    container._setObject(id, object)
    if REQUEST is not None:
        url = container.absolute_url()
        REQUEST.RESPONSE.redirect('%s/manage_main' % url)
