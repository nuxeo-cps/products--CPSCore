# -*- coding: iso-8859-15 -*-
# (C) Copyright 2004 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Anguenot <ja@nuxeo.com>
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

""" Expressions in a CPS web-configurable workflow.

Extends DCWorkflow Expression for CPS.
"""

from  Globals import InitializeClass

from Globals import Persistent
from Acquisition import aq_inner, aq_parent
from AccessControl import getSecurityManager

from Products.PageTemplates.Expressions import getEngine
from Products.PageTemplates.Expressions import SecureModuleImporter

from Products.DCWorkflow.Expression import StateChangeInfo

class CPSStateChangeInfo(StateChangeInfo):
    """Provides information for expressions and scripts.

    Extends DCWorkflow Expression
    """

    def __init__(self, object, workflow, status=None, transition=None,
                 old_state=None, new_state=None, delegatees=None, kwargs=None):

        StateChangeInfo.__init__(self, object, workflow, status, transition,
                                 old_state, new_state, kwargs)
        self.delegatees = delegatees

    def getLanguageRevisions(self):
        ob = self.object
        return {ob.getLanguage(): ob.getRevision()}

    def getDelegateesVarInfoFor(self, var_id=''):
        """Return the data structure object holding the delegatees for the
        workflow variable var_id
        """
        if self.delegatees is not None:
            return self.delegatees.get(var_id, None)
        return None

    def getAllDelegateesVarInfo(self):
        """Return all the delegatees variables information

        Dictionnary holding information for all the defined delegatees
        variables.

        The key is the workflow wariable id.
        The value is the data structure
        """
        if self.delegatees is not None:
            return self.delegatees
        return {}

InitializeClass(CPSStateChangeInfo)

def createExprContext(sci):
    '''
    An expression context provides names for TALES expressions.
    '''
    ob = sci.object
    wf = sci.workflow
    data = {
        'here':         ob,
        'container':    aq_parent(aq_inner(ob)),
        'nothing':      None,
        'root':         wf.getPhysicalRoot(),
        'request':      getattr( ob, 'REQUEST', None ),
        'modules':      SecureModuleImporter,
        'user':         getSecurityManager().getUser(),
        'state_change': sci,
        'transition':   sci.transition,
        'status':       sci.status,
        'delegatees':   sci.delegatees,
        'kwargs':       sci.kwargs,
        'workflow':     wf,
        'scripts':      wf.scripts,
        }
    return getEngine().getContext(data)
