# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""PatchOFSFolder

Monkey-patches Folder to provide basic OrderedFolder behavior.
"""

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from OFS.Folder import Folder
from OFS.OrderSupport import OrderSupport
from Products.CPSCore.CPSCorePermissions import ChangeSubobjectsOrder

try:
    import Products.OrderedFolderSupportPatch
    raise ImportError("Product OrderedFolderSupportPatch is not compatible "
                      "with this version of CPS")
except ImportError:
    pass


security = ClassSecurityInfo()

info = (
    # Method                     Old CPS compatibility    Protected
    ('moveObjectsByDelta',       '',                        True),
    ('moveObjectsUp',            'move_object_up',          True),
    ('moveObjectsDown',          'move_object_down',        True),
    ('moveObjectsToTop',         'move_object_to_top',      True),
    ('moveObjectsToBottom',      'move_object_to_bottom',   True),
    ('getObjectPosition',        'get_object_position',     True),
    ('moveObjectToPosition',     'move_object_to_position', True),
    ('_old_manage_renameObject', '',                        False),
    ('manage_renameObject',      '',                        False),
    )
for name, compat, protect in info:
    method = getattr(OrderSupport, name)
    setattr(Folder, name, method)
    if protect:
        security.declareProtected(ChangeSubobjectsOrder, name)
    if compat:
        setattr(Folder, compat, method)
        security.declareProtected(ChangeSubobjectsOrder, compat)

Folder.security = security
InitializeClass(Folder)
