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
"""Mixin that does TypesTool-like operation on types.
"""

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Acquisition import aq_base

from ExtensionClass import Base

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation


class TypeConstructor(Base):

    security = ClassSecurityInfo()

    #
    # This does object construction like TypesTool but without security
    # checks (which are already done by WorkflowTool).
    #

    # This should be somewhere in CMFCore.TypesTool...

    def _constructInstance_fti(self, ti, id, *args, **kw):
        if not ti.product or not ti.factory:
            raise ValueError('Product factory for %s was undefined: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        p = self.manage_addProduct[ti.product]
        meth = getattr(p, ti.factory, None)
        if meth is None:
            raise ValueError('Product factory for %s was invalid: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        if getattr(aq_base(meth), 'isDocTemp', 0):
            newid = meth(meth.aq_parent, self.REQUEST, id=id, *args, **kw)
        else:
            newid = meth(id, *args, **kw)
        newid = newid or id
        return self._getOb(newid)

    def _constructInstance_sti(self, ti, id, *args, **kw):
        constr = self.restrictedTraverse(ti.constructor_path)
        constr = aq_base(constr).__of__(self)
        return constr(self, id, *args, **kw)

    security.declarePrivate('constructContent')
    def constructContent(self, type_name, id, final_type_name=None,
                         *args, **kw):
        """Construct an CMFish object without all the security checks.

        Do not insert into any workflow.

        Returns the object.
        """
        ttool = getToolByName(self, 'portal_types')
        ti = ttool.getTypeInfo(type_name)
        if ti is None:
            raise ValueError('No type information for %s' % type_name)
        if isinstance(ti, FactoryTypeInformation):
            ob = self._constructInstance_fti(ti, id, *args, **kw)
        elif isinstance(ti, ScriptableTypeInformation):
            ob = self._constructInstance_sti(ti, id, *args, **kw)
        else:
            raise ValueError('Unknown type information class for %s' %
                             type_name)
        if ob.getId() != id:
            # Sanity check
            raise ValueError('Constructing %s, id changed from %s to %s' %
                             (type_name, id, ob.getId()))
        if final_type_name is None:
            final_type_name = type_name
        ob._setPortalTypeName(final_type_name)
        ob.reindexObject(idxs=['portal_type', 'Type'])
        # XXX should notify something
        return ob

InitializeClass(TypeConstructor)


class TypeContainer(Base):

    security = ClassSecurityInfo()

    #
    # Copy without security checks.
    #

    security.declarePrivate('copyContent')
    def copyContent(self, ob, id):
        """Copy an object without all the security checks.

        Similar to manage_clone.
        Returns the new object.
        """
        # This code is derived from CopySupport.CopyContainer.manage_clone
        if not ob.cb_isCopyable():
            raise CopyError, 'Copy not supported: %s' % ob.getId()
        try:
            self._checkId(id)
        except: # Huh, stupid string exceptions...
            raise CopyError, 'Invalid id: %s' % (id,)
        try:
            ob._notifyOfCopyTo(self, op=0)
        except:
            raise CopyError, 'Clone Error: %s' % (sys.exc_info()[1],)
        ob = ob._getCopy(self)
        ob._setId(id)
        self._setObject(id, ob)
        ob = self._getOb(id)
        ob.manage_afterClone(ob)
        if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
            on.manage_afterCMFAdd(ob, self)
        return ob

InitializeClass(TypeContainer)
