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

import sys
from zLOG import LOG, INFO
from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import copy_or_move
from Acquisition import aq_base, aq_parent, aq_inner

from ExtensionClass import Base
from OFS import Moniker
from OFS.CopySupport import CopyError, _cb_decode, sanity_check

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation
from Products.CPSCore.cpsutils import _isinstance
try:
    from Products.CPSDocument.FlexibleTypeInformation import FlexibleTypeInformation
except ImportError:
    LOG('CPSCore', INFO, 'No CPSDocument found, ignoring type.')
    class FlexibleTypeInformation:
        pass


class TypeConstructor(Base):

    security = ClassSecurityInfo()

    #
    # This allows a folderish class to have it do correct CPS creation
    # when invokeFactory is called.
    #

    security.declarePublic('invokeFactory')
    def invokeFactory(self, type_name, id, RESPONSE=None, *args, **kw):
        """Create a CMF object in this folder.

        A creation_transitions argument should be passed for CPS
        object creation.

        This method is public as creation security is governed
        by the workflows allowed by the workflow tool.
        """
        wftool = getToolByName(self, 'portal_workflow')
        newid = wftool.invokeFactoryFor(self, type_name, id, *args, **kw)
        if RESPONSE is not None:
            ob = self._getOb(newid)
            ttool = getToolByName(self, 'portal_types')
            info = ttool.getTypeInfo(type_name)
            RESPONSE.redirect('%s/%s' % (ob.absolute_url(),
                                         info.immediate_view))
        return newid

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

    def _constructInstance_flexti(self, ti, id, *args, **kw):
        container = self
        return ti._constructInstance(container, id, *args, **kw)

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
        if _isinstance(ti, FactoryTypeInformation):
            ob = self._constructInstance_fti(ti, id, *args, **kw)
        elif _isinstance(ti, ScriptableTypeInformation):
            ob = self._constructInstance_sti(ti, id, *args, **kw)
        elif _isinstance(ti, FlexibleTypeInformation):
            ob = self._constructInstance_flexti(ti, id, *args, **kw)
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
            ob.manage_afterCMFAdd(ob, self)
        return ob

    #
    # CPS Cut/Copy/Paste
    #

    security.declareProtected(copy_or_move, 'manage_CPScopyObjects')
    def manage_CPScopyObjects(self, ids, REQUEST=None):
        """Copy objects (for later paste)."""
        wftool = getToolByName(self, 'portal_workflow')
        ok, why = wftool.isBehaviorAllowedFor(self, 'copy', get_details=1)
        if not ok:
            raise CopyError, 'Copy not allowed, %s' % why
        return self.manage_copyObjects(ids, REQUEST=REQUEST)

    security.declareProtected(copy_or_move, 'manage_CPScutObjects')
    def manage_CPScutObjects(self, ids, REQUEST=None):
        """Cut objects (for later paste)."""
        wftool = getToolByName(self, 'portal_workflow')
        ok, why = wftool.isBehaviorAllowedFor(self, 'cut', get_details=1)
        if not ok:
            raise CopyError, 'Cut not allowed, %s' % why
        return self.manage_cutObjects(ids, REQUEST=REQUEST)

    security.declareProtected(copy_or_move, 'manage_CPSpasteObjects')
    def manage_CPSpasteObjects(self, cp):
        """Paste objects (from an earlier copy)."""
        wftool = getToolByName(self, 'portal_workflow')
        pxtool = getToolByName(self, 'portal_proxies')
        try:
            cp = _cb_decode(cp)
        except: # XXX
            raise CopyError, 'Invalid copy data.'

        # Verify pastable into self.
        ok, why = wftool.isBehaviorAllowedFor(self, 'paste', get_details=1)
        if not ok:
            raise CopyError, 'Paste not allowed, %s' % why

        op = cp[0]
        root = self.getPhysicalRoot()

        oblist = []
        containers = []
        behavior = (op == 0) and 'copy' or 'cut'
        for mdata in cp[1]:
            m = Moniker.loadMoniker(mdata)
            try:
                ob = m.bind(root)
            except: # XXX
                raise CopyError, 'Object not found'
            # Verify copy/cutable from source container.
            container = aq_parent(aq_inner(ob))
            if container not in containers:
                ok, why = wftool.isBehaviorAllowedFor(container, behavior,
                                                      get_details=1)
                if not ok:
                    raise CopyError, '%s not allowed, %s' % (behavior, why)
                containers.append(container)
            oblist.append(ob)

        result = []
        containers = []
        if op == 0:
            # Copy operation
            for ob in oblist:
                orig_id = ob.getId()
                if not ob.cb_isCopyable():
                    raise CopyError, 'Copy not supported for %s' % orig_id
                ob._notifyOfCopyTo(self, op=0)
                ob = ob._getCopy(self)
                id = self._get_id(orig_id)
                result.append({'id':orig_id, 'new_id':id})
                ob._setId(id)
                self._setObject(id, ob)
                ob = self._getOb(id)
                ob.manage_afterClone(ob)
                # unshare content after copy
                pxtool.unshareContent(ob)
                # notify interested parties
                if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
                    ob.manage_afterCMFAdd(ob, self)
        elif op == 1:
            # Move operation
            for ob in oblist:
                orig_id = ob.getId()
                if not ob.cb_isMoveable():
                    raise CopyError, 'Move not supported for %s' % orig_id
                ob._notifyOfCopyTo(self, op=1)
                if not sanity_check(self, ob):
                    raise CopyError, 'This object cannot be pasted into itself'

                # try to make ownership explicit so that it gets carried
                # along to the new location if needed.
                ob.manage_changeOwnershipType(explicit=1)

                aq_parent(aq_inner(ob))._delObject(orig_id)
                ob = aq_base(ob)
                id = self._get_id(orig_id)
                result.append({'id':orig_id, 'new_id':id })
                ob._setId(id)
                self._setObject(id, ob, set_owner=0)
                # try to make ownership implicit if possible
                ob = self._getOb(id)
                ob.manage_changeOwnershipType(explicit=0)
                # notify interested parties
                if hasattr(aq_base(ob), 'manage_afterCMFAdd'):
                    ob.manage_afterCMFAdd(ob, self)

        return result

InitializeClass(TypeContainer)
