# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
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

from Products.CMFCore.RegistrationTool import RegistrationTool
import re
from Products.CMFCore.utils import getToolByName

# Patching the class
__ALLOWED_MEMBER_ID_PATTERN = re.compile("^[a-zA-Z][a-zA-Z0-9@\-\._]*$")
RegistrationTool.__ALLOWED_MEMBER_ID_PATTERN = __ALLOWED_MEMBER_ID_PATTERN

def isMemberIdAllowed(self, id):
    """Returns 1 if the ID is not in use, is not reserved and the corresponding
    homeFolder doesn't already exists.
    """
    if len(id) < 1 or id == 'Anonymous User':
        return 0
    if not self.__ALLOWED_MEMBER_ID_PATTERN.match(id):
        return 0
    membership = getToolByName(self, 'portal_membership')
    if (membership.getMemberById(id) is not None
        or membership.homeFolderExists(id)):
        return 0
    return 1

# Patching the class
RegistrationTool.isMemberIdAllowed = isMemberIdAllowed
