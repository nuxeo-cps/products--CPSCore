# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
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
from ComputedAttribute import ComputedAttribute
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.CMFCorePermissions import AccessContentsInformation

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

    security.declarePrivate('setVersionInfos')
    def setVersionInfos(self, version_infos):
        """Set the version infos for this proxy.

        The version infos is a dict of language -> version,
        where language can be '*' for the default, and version
        is an integer.
        """
        self._version_infos = version_infos.copy()

    security.declarePrivate('getVersionInfos')
    def getVersionInfos(self):
        """Return the version infos for this proxy."""
        return self._version_infos.copy()

    security.declarePrivate('getRepoId')
    def getRepoId(self):
        """Return the repoid for this proxy."""
        return self._repoid

    security.declareProtected(AccessContentsInformation, 'getContent')
    def getContent(self, lang=None):
        """Return the content object referred to by this proxy."""
        pxtool = getToolByName(self, 'portal_proxies', None)
        if pxtool is None:
            LOG('ProxyBase', DEBUG, 'No portal_proxies found')
            return None
        hubtool = getToolByName(self, 'portal_eventservice', None)
        if hubtool is None:
            LOG('ProxyBase', DEBUG, 'No portal_eventservice found')
            return None
        hubid = hubtool.getHubId(self)
        if hubid is None:
            LOG('ProxyBase', ERROR,
                'No hubid found for %s' % '/'.join(self.getPhysicalPath()))
            return None
        return pxtool.getMatchedObject(hubid, lang=lang)

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
        return self.getId()

    security.declarePublic('SearchableText')
    def SearchableText(self):
        """No searchable text."""
        return ''

    #
    # ZMI
    #

    _properties = (
        {'id':'RepoId', 'type':'string', 'mode':''},
        {'id':'VersionInfos', 'type':'string', 'mode':''},
        )
    RepoId = ComputedAttribute(getRepoId, 1)
    VersionInfos = ComputedAttribute(getVersionInfos, 1)

InitializeClass(ProxyBase)


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
    )

class ProxyFolder(ProxyBase, CPSBaseFolder):
    """A proxy folder is a folder whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy Folder'
    # portal_type will be set to the target's portal_type after creation

    def __init__(self, id, repoid=None, version_infos=None):
        CPSBaseFolder.__init__(self, id)
        ProxyBase.__init__(self, repoid, version_infos)

InitializeClass(ProxyFolder)


class ProxyDocument(ProxyBase, CPSBaseDocument):
    """A proxy document is a document whose data is indirected to a document
    in a repository."""

    meta_type = 'CPS Proxy Document'
    # portal_type will be set to the target's portal_type after creation

    def __init__(self, id, repoid=None, version_infos=None):
        CPSBaseDocument.__init__(self, id)
        ProxyBase.__init__(self, repoid, version_infos)

InitializeClass(ProxyDocument)


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
