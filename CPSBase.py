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

from OFS.ObjectManager import ObjectManager
from OFS.PropertyManager import PropertyManager
from OFS.FindSupport import FindSupport

from Products.CMFCore.CMFCorePermissions import View, AddPortalContent
from Products.CMFCore.CMFCorePermissions import ModifyPortalContent
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCatalogAware import CMFCatalogAware
from Products.CMFCore.PortalFolder import PortalFolder
from Products.CMFCore.PortalContent import PortalContent
from Products.CMFDefault.DublinCore import DefaultDublinCoreImpl


defaultencoding = sys.getdefaultencoding()


class CPSBaseDocument(CMFCatalogAware, PortalFolder, PortalContent,
                      DefaultDublinCoreImpl, PropertyManager):
    """The base from which all CPS content objects derive."""

    meta_type = 'CPS Base Document'
    portal_type = None

    #_isDiscussable = 1
    isPrincipiaFolderish = 0

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

    security.declareProtected(ModifyPortalContent, 'edit')
    def edit(self, **kw):
        """Edit the document."""
        self.manage_changeProperties(**kw)
        self.reindexObject()
        # XXX notify event of modify

    security.declareProtected(View, 'SearchableText')
    def SearchableText(self):
        """The searchable text for this object.

        Automatically derived from all string properties.
        """
        values = self.propertyValues()
        strings = []
        for val in values:
            t = type(val)
            if isinstance(t, StringType) or isinstance(t, UnicodeType):
                strings.append(val)
                continue
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


class CPSBaseFolder(CPSBaseDocument):
    """The base from which all CPS folder objects derive."""

    meta_type = 'CPS Base Folder'

    isPrincipiaFolderish = 1

    security = ClassSecurityInfo()

    #
    # This allows a folderish class to have it do correct CPS creation
    # when invokeFactory is called.
    #

    security.declareProtected(AddPortalContent, 'invokeFactory')
    def invokeFactory(self, type_name, id, RESPONSE=None, *args, **kw):
        """Create a CMF object in this folder.

        A creation_transitions argument should be passed for CPS
        object creation.
        Creation is governed by the workflows allowed by the workflow tool.
        """
        wftool = getToolByName(self, 'portal_workflow')
        newid = wftool.invokeFactoryFor(self, type_name, id, *args, **kw)
        if RESPONSE is not None:
            ob = self._getOb(newid)
            ttool = getToolByName(self, 'portal_types')
            info = ttool.getTypeInfo(type_name)
            RESPONSE.redirect('%s/%s' % (ob.absolute_url(),
                                         info.immediate_view))
        return newid

    security.declarePrivate('invokeFactoryCMF')
    def invokeFactoryCMF(self, type_name, id, RESPONSE=None, *args, **kw):
        """Original CMF factory invocation."""
        return PortalFolder.invokeFactory(self, type_name, id,
                                          RESPONSE=RESPONSE, *args, **kw)

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


def CPSBase_adder(container, ob, REQUEST=None):
    """Adds a just constructed object to its container."""
    # When called from the ZMI, container is a dispatcher.
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        url = container.absolute_url()
        REQUEST.RESPONSE.redirect('%s/manage_main' % url)
