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
"""Tests for the CPS Workflow Tool.
"""

import Zope
import unittest

from Products.CMFCore.tests.base.testcase import SecurityRequestTest

from OFS.Folder import Folder
from OFS.SimpleItem import SimpleItem

from Products.NuxCPS3.CPSWorkflow import CPSWorkflowDefinition
from Products.NuxCPS3.CPSWorkflow import TRIGGER_CREATION
from Products.NuxCPS3.CPSWorkflowConfiguration import addCPSWorkflowConfiguration
from Products.NuxCPS3.CPSWorkflowTool import CPSWorkflowConfig_id


class Dummy(SimpleItem):
    def __init__(self, id):
        self._id = id

    def getId(self):
        return self._id

class DummyTypeInfo(Dummy):
    pass

class DummyContent(Dummy):
    meta_type = 'Dummy'
    _isPortalContent = 1

    def _getPortalTypeName(self):
        return 'Dummy Content'

class DummyTypesTool(SimpleItem):
    def listTypeInfo( self ):
        return [DummyTypeInfo('Dummy Content')]

    def getTypeInfo(self, ob):
        if (ob == 'Dummy Content' or
            getattr(ob, 'meta_type', None) == 'Dummy'):
            return DummyTypeInfo('Dummy Content')
        return None



class WorkflowToolTests(SecurityRequestTest):
    """Test CPS Workflow Tool."""

    def setUp(self):
        SecurityRequestTest.setUp(self)

        self.root = Folder()
        self.root.id = 'root'
        root = self.root

        from Products.CMFCore.WorkflowTool import addWorkflowFactory
        addWorkflowFactory(CPSWorkflowDefinition, id='cps wfdef')

        from Products.NuxCPS3.CPSWorkflowTool import addCPSWorkflowTool
        addCPSWorkflowTool(root)

    def tearDown( self ):
        from Products.CMFCore.WorkflowTool import _removeWorkflowFactory
        _removeWorkflowFactory(CPSWorkflowDefinition, id='cps wfdef')

        SecurityRequestTest.tearDown(self)

    ##########

    def makeWorkflows(self):
        id = 'wf'
        wf = CPSWorkflowDefinition(id)
        self.root.portal_workflow._setObject(id, wf)
        wf = self.root.portal_workflow.wf
        ct = wf.getCreationTransitions(self.root)
        self.assertEqual(tuple(ct), ())
        # create states
        wf.states.addState('s1')
        states = list(wf.states.objectIds())
        states.sort()
        self.assertEqual(tuple(states), ('s1',))
        # create transition
        wf.transitions.addTransition('t1')
        t1 = wf.transitions.get('t1')
        t1.setProperties('title', 's1', trigger_type=TRIGGER_CREATION)
        transitions = wf.transitions.objectIds()
        self.assertEqual(tuple(transitions), ('t1',))
        # another empty workflow
        id2 = 'wf2'
        wf2 = CPSWorkflowDefinition(id2)
        self.root.portal_workflow._setObject(id2, wf2)

    def makeTypes(self):
        self.root._setObject('portal_types', DummyTypesTool())

    def makeTree(self):
        f = Folder()
        f.id = 'f'
        self.root._setObject(f.id, f)
        f = self.root.f
        dummy = DummyContent('dummy')
        f._setObject(dummy.getId(), dummy)

    ##########

    def test_wf_getCreationTransitions(self):
        self.makeWorkflows()
        ct = self.root.portal_workflow.wf.getCreationTransitions(self.root)
        self.assertEqual(tuple(ct), ('t1',))

    def test_wft_getCreationTransitions(self):
        self.makeWorkflows()
        self.makeTypes()
        wft = self.root.portal_workflow
        wft.setChainForPortalTypes(('Dummy Content',), ('wf',))
        # setup container
        f = Folder()
        f.id = 'f'
        self.root._setObject(f.id, f)
        f = self.root.f
        # check default available
        ct = wft.getCreationTransitions(f, 'Dummy Content')
        self.assertEqual(ct, {'wf': ('t1',)})

    def test_wft_getChainFor(self):
        self.makeWorkflows()
        self.makeTypes()
        self.makeTree()
        wft = self.root.portal_workflow
        f = self.root.f
        # check default
        chain = wft.getChainFor('Dummy Content', f)
        self.assertEqual(tuple(chain), ())
        # check global chain
        wft.setChainForPortalTypes(('Dummy Content',), ('wf',))
        chain = wft.getChainFor('Dummy Content', f)
        self.assertEqual(tuple(chain), ('wf',))
        # check global chain, using object
        dummy = f.dummy
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ('wf',))
        # remove global chain
        wft.setChainForPortalTypes(('Dummy Content',), ())
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ())

    def test_wft_getChainFor_placeful(self):
        self.makeWorkflows()
        self.makeTypes()
        self.makeTree()
        wft = self.root.portal_workflow
        f = self.root.f
        f2 = Folder()
        f2.id = 'f2'
        f._setObject(f2.id, f2)
        f2 = f.f2
        # setup placeful workflows
        addCPSWorkflowConfiguration(f)
        config = getattr(f, CPSWorkflowConfig_id)
        config.setChain('Dummy Content', ('wf',))
        # check placeful
        dummy = f.dummy
        chain = wft.getChainFor(dummy)
        self.assertEqual(tuple(chain), ('wf',))
        # add new sub folder
        addCPSWorkflowConfiguration(f2)
        config2 = getattr(f2, CPSWorkflowConfig_id)
        config2.setChain('Dummy Content', ('wf2',))
        # check inheritance order
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf2',))
        # check empty chain
        config2.setChain('Dummy Content', ())
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ())
        # check inheritance when no config
        config2.delChain('Dummy Content')
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf',))
        # check default
        wft.setDefaultChain('wf2')
        config2.setChain('Dummy Content', None)
        chain = wft.getChainFor('Dummy Content', f2)
        self.assertEqual(tuple(chain), ('wf2',))


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(WorkflowToolTests)

if __name__ == '__main__':
    unittest.TextTestRunner().run(test_suite())
