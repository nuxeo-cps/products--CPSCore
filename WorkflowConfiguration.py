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
"""Workflow configuration object.

This is a placeful definition of the portal_type -> workflow chain
mapping.
"""

from zLOG import LOG, ERROR, DEBUG
from types import StringType
from Acquisition import aq_base, aq_parent, aq_inner
from Globals import InitializeClass, DTMLFile, PersistentMapping
from AccessControl import ClassSecurityInfo, Unauthorized

from OFS.SimpleItem import SimpleItem

from Products.CMFCore.utils import getToolByName, _checkPermission
from Products.CMFCore.CMFCorePermissions import AddPortalContent
from Products.CMFCore.WorkflowTool import WorkflowTool


WorkflowConfiguration_meta_type = 'CPS Workflow Configuration'
WorkflowConfiguration_id = '.portal_workflow_configuration'

class WorkflowConfiguration(SimpleItem):
    """Workflow Configuration.

    A workflow configuration object describes placefully what workflow
    chain is to be used for what portal_type.
    """

    id = WorkflowConfiguration_id
    meta_type = WorkflowConfiguration_meta_type
    portal_type = None

    security = ClassSecurityInfo()

    def __init__(self):
        self._chains_by_type = PersistentMapping()
        # None is the default chain.
        # If a key is present, the the chain is overloaded,
        # otherwise the acquired config must be used.

    security.declarePrivate('_getPlacefulChainFor')
    def _getPlacefulChainFor(self, portal_type):
        """Get the chain for the given portal_type.

        Returns None if no placeful chain is found.
        """
        chain = self._chains_by_type.get(portal_type)
        if chain is not None:
            return chain
        # Ask above.
        parent = aq_parent(aq_inner(self))
        higher_conf = parent.aq_acquire(WorkflowConfiguration_id,
                                        default=None, containment=1)
        if higher_conf is not None:
            return higher_conf._getPlacefulChainFor(portal_type)
        # Nothing placeful found.
        return None

InitializeClass(WorkflowConfiguration)

def addWorkflowConfiguration(container, REQUEST=None):
    """Add a Workflow Configuration."""
    # container is a dispatcher when called from ZMI
    ob = WorkflowConfiguration()
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')
