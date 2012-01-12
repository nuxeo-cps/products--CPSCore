# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
"""This file contains all patches for the CMFCore product."""

from ZODB.loglevels import TRACE
from logging import getLogger
logger = getLogger(__name__)

# Patch mergedLocalRoles to use aclu mergedLocalRoles if any
from Products.CMFCore import utils
from Products.CPSCore.utils import mergedLocalRoles
logger.log(TRACE, "Patched mergedLocalRoles to use aclu")
utils.mergedLocalRoles = mergedLocalRoles
utils._mergedLocalRoles = mergedLocalRoles

# Patch TypesTool so that TypeInformation's properties are editable.
import typestool

# Patching CatalogTool to handle proxies search
import catalog

# make the Five Actions Tool easy to be registered as a provider
from Products.CMFCore.exportimport import actions
actions._SPECIAL_PROVIDERS += ('portal_fiveactions',)

import portalfolder
