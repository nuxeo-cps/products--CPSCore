# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Jalon <jj@nuxeo.com>
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

from Globals import InitializeClass, DTMLFile
from OFS.Folder import Folder
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import UniqueObject, getToolByName
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens

class MirrorTool(UniqueObject, Folder):
    """Mirror Tool just mirrors the site hierarchy.

    It recreates under portal_mirror the same hierarchy of folderish
    objects (with Folders).
    It's a simple example of what you can do with event service.

    You have to register portal_mirror in portal_eventservice
    so portal_mirror is notifyied on any addition/deletion of object.
    """

    id = 'portal_mirror'

    meta_type = 'CPS Mirror Tool'

    security = ClassSecurityInfo()

    security.declarePrivate('notify_mirror')
    def notify_mirror(self, event_type, object, infos):
        if event_type not in ['sys_add_object', 'sys_del_object']:
            return
        if not object.isPrincipiaFolderish:
            return
        object_id = object.getId()
        if object_id.startswith('portal_'):
            return
        utool = getToolByName(self, 'portal_url')
        rel_url = utool.getRelativeUrl(object)
        if rel_url.startswith('portal_'):
            return
        path = rel_url.split('/')
        base_path = path[:-1]
        base = self.restrictedTraverse(base_path, None)
        if base is None:
            return
        if event_type == 'sys_add_object':
            f = Folder()
            f.id = object_id
            f.title = object.title
            base._setObject(object_id, f)
        elif event_type == 'sys_del_object':
            if object_id in base.objectIds():
                base.manage_delObjects([object_id])

InitializeClass(MirrorTool)
