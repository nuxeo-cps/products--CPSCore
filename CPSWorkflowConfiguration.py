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
"""CPS workflow configuration object.

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

from CPSWorkflowPermissions import ManageWorkflows

from Products.NuxCPS3.CPSWorkflowTool import CPSWorkflowConfig_id


class CPSWorkflowConfiguration(SimpleItem):
    """Workflow Configuration.

    A workflow configuration object describes placefully what workflow
    chain are to be used for what portal_type.
    """

    id = CPSWorkflowConfig_id
    meta_type = 'CPS Workflow Configuration'
    portal_type = None

    security = ClassSecurityInfo()

    def __init__(self):
        self._chains_by_type = PersistentMapping()
        # The None value means "use the default chain".
        # If a key is present, then the chain is overloaded,
        #    otherwise any acquired config is used.
        # XXX There is no way to override locally the default chain...

    #
    # API called by CPS Workflow Tool
    #

    def _get_chain_or_default(self, portal_type):
        """Return the chain for portal_type, or the Default chain."""
        chain = self._chains_by_type[portal_type]
        if chain is not None:
            return chain
        wftool = getToolByName(self, 'portal_workflow')
        # May want to revisit this if we want to placefully override Default
        return wftool.getDefaultChainFor(portal_type)

    security.declarePrivate('getPlacefulChainFor')
    def getPlacefulChainFor(self, portal_type):
        """Get the chain for the given portal_type.

        Returns None if no placeful chain is found.
        Acquires from parent configurations if needed.
        """
        if self._chains_by_type.has_key(portal_type):
            return self._get_chain_or_default(portal_type)
        # Ask above.
        parent = aq_parent(aq_inner(aq_parent(aq_inner(self))))
        try:
            higher_conf = parent.aq_acquire(CPSWorkflowConfig_id,
                                            containment=1)
        except AttributeError:
            # Nothing placeful found.
            return None
        return higher_conf.getPlacefulChainFor(portal_type)

    #
    # Internal API
    #

    security.declareProtected(ManageWorkflows, 'setChain')
    def setChain(self, portal_type, chain):
        """Set the chain for a portal type."""
        wftool = getToolByName(self, 'portal_workflow')
        if chain is not None:
            for wf_id in chain:
                if not wftool.getWorkflowById(wf_id):
                    raise ValueError, (
                        '"%s" is not a workflow ID.' % wf_id)
            chain = tuple(chain)
        self._chains_by_type[portal_type] = chain

    security.declareProtected(ManageWorkflows, 'delChain')
    def delChain(self, portal_type):
        """Delete the chain for a portal type."""
        del self._chains_by_type[portal_type]

    #
    # ZMI
    #

    manage_options = ({'label' : 'Workflows',
                       'action' : 'manage_editForm',
                       },
                      ) + SimpleItem.manage_options

    _manage_editForm = DTMLFile('zmi/workflowConfigurationEditForm', globals())

    security.declareProtected(ManageWorkflows, 'manage_editForm')
    def manage_editForm(self, REQUEST=None):
        """The edit form."""
        ttool = getToolByName(self, 'portal_types')
        cbt = self._chains_by_type
        types_info = []
        addable_info = []
        for ti in ttool.listTypeInfo():
            id = ti.getId()
            title = ti.Title()
            if cbt.has_key(id):
                chain = cbt[id]
                if chain is not None:
                    chain_str = ', '.join(chain)
                else:
                    chain_str = '(Default)'
                if title == id:
                    title = None
                types_info.append({'id': id,
                                   'title': title,
                                   'chain': chain_str})
            else:
                if title != id:
                    title = '%s (%s)' % (title, id)
                addable_info.append({'id': id,
                                     'title': title})
        return self._manage_editForm(REQUEST,
                                     types_info=types_info,
                                     addable_info=addable_info)

    security.declareProtected(ManageWorkflows, 'manage_editChains')
    def manage_editChains(self,
                          sub_save=None, sub_del=None,
                          REQUEST=None):
        """Edit the chains."""
        kw = REQUEST.form
        ttool = getToolByName(self, 'portal_types')
        if sub_save is not None:
            cbt = self._chains_by_type
            for ti in ttool.listTypeInfo():
                id = ti.getId()
                if not cbt.has_key(id):
                    continue
                chain = kw.get('chain_%s' % id)
                if chain is None:
                    continue
                if chain == '(Default)':
                    chain = None
                else:
                    chain = chain.split(',')
                    chain = [wf.strip() for wf in chain if wf.strip()]
                self.setChain(id, chain)
            if REQUEST is not None:
                REQUEST.set('manage_tabs_message', 'Saved.')
                return self.manage_editForm(REQUEST)
        elif sub_del is not None:
            cbt = self._chains_by_type
            for ti in ttool.listTypeInfo():
                id = ti.getId()
                if not cbt.has_key(id):
                    continue
                if kw.has_key('cb_%s' % id):
                    self.delChain(id)
            if REQUEST is not None:
                REQUEST.set('manage_tabs_message', 'Deleted.')
                return self.manage_editForm(REQUEST)

    security.declareProtected(ManageWorkflows, 'manage_addChain')
    def manage_addChain(self, portal_type, chain, REQUEST=None):
        """Add a chains."""
        chain = chain.strip()
        if chain == '(Default)':
            chain = None
        else:
            chain = chain.split(',')
            chain = [wf.strip() for wf in chain if wf.strip()]
        self.setChain(portal_type, chain)
        if REQUEST is not None:
            REQUEST.set('manage_tabs_message', 'Added.')
            return self.manage_editForm(REQUEST)

InitializeClass(CPSWorkflowConfiguration)

def addCPSWorkflowConfiguration(container, REQUEST=None):
    """Add a Workflow Configuration."""
    # container is a dispatcher when called from ZMI
    ob = CPSWorkflowConfiguration()
    id = ob.getId()
    container._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(container.absolute_url()+'/manage_main')
