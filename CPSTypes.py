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

from ExtensionClass import Base


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
        if final_type_name is not None:
            final_type_name = type_name
        ob._setPortalTypeName(final_type_name)
        ob.reindexObject(idxs=['portal_type', 'Type'])
        return ob

InitializeClass(TypeConstructor)
