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

from zLOG import LOG, ERROR, DEBUG
import random
from Globals import InitializeClass
from Acquisition import aq_base
from AccessControl import ClassSecurityInfo

from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.PortalFolder import PortalFolder
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation

from Products.NuxCPS3.CPSWorkflowTool import CPSWorkflowConfig_id


class NoWorkflowConfiguration:
    """Class for a workflow configuration object that denies
    all workflows."""

    security = ClassSecurityInfo()

    security.declarePrivate('getPlacefulChainFor')
    def getPlacefulChainFor(self, portal_type):
        """No workflow chain is allowed."""
        return ()

InitializeClass(NoWorkflowConfiguration)



# XXX we'll want a btreefolder2 here, not a folder
class ObjectRepository(UniqueObject, PortalFolder):
    """An object repository stores objects that can be
    available in several versions.

    It can be queried for the best version of a given object matching
    a set of constraints, for instance on language.

    repoid is an identifier unique to the repository that describes a set
    of versions of one object.
    """

    id = 'portal_repository'
    meta_type = 'CPS Repository Tool'
    portal_type = meta_type

    security = ClassSecurityInfo()

    def __init__(self):
        pass

    #
    # API
    #

    security.declarePrivate('invokeFactory')
    def invokeFactory(self, type_name,
                      repoid=None, version_info=None,
                      *args, **kw):
        """Create an object with repoid and version in the repository.

        If repoid is None, a new one is generated
        If version_info is None, 1 is used.
        Returns the used repoid and version.
        """
        if version_info is None:
            version_info = 1
        if repoid is None:
            while 1:
                repoid = str(random.randrange(1,2147483600))
                id = self._get_id(repoid, version_info)
                if not hasattr(self, id):
                    break
        else:
            id = self._get_id(repoid, version_info)
            if hasattr(self, id):
                raise ValueError('A document with repoid=%s and version=%s '
                                 'already exists' % (repoid, version_info))
        self.constructContent(type_name, id, *args, **kw)
        return (repoid, version_info)

    # XXX used for what?
    security.declarePrivate('addObjectVersion')
    def addObjectVersion(self, object, repoid, version_info):
        """Add the version version_info of the object repoid.

        repoid is a unique id.
        version_info is an integer describing the version.
        If repoid is None (new object without previous versions), a new
        one is created and returned.
        """
        id = self._get_id(repoid, version_info)
        object._setId(id)
        self._setObject(id, object)
        return id

    security.declarePrivate('delObjectVersion')
    def delObjectVersion(self, repoid, version_info):
        """Delete a version of an object."""
        id = self._get_id(repoid, version_info)
        self._delObject(id)

    security.declarePrivate('getObjectVersion')
    def getObjectVersion(self, repoid, version_info):
        """Get a version of an object."""
        id = self._get_id(repoid, version_info)
        return self._getOb(id)

    security.declarePrivate('delObject')
    def delObject(self, repoid):
        """Delete all the versions of an object."""
        prefix = self._get_id_prefix(repoid)
        for id in self.objectIds():
            if id.startswith(prefix):
                self._delObject(id)

    security.declarePrivate('listAll')
    def listAll(self):
        """List all (repoid, version_info) in the repository."""
        items = []
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            items.append((repoid, version_info))
        return items

    security.declarePrivate('listRepoIds')
    def listRepoIds(self):
        """List all the repoids in the repository."""
        idd = {}
        has = idd.has_key
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            if has(repoid):
                continue
            idd[repoid] = None
        return idd.keys()

    security.declarePrivate('listVersions')
    def listVersions(self, repoid):
        """List all the versions of a given object."""
        rid = repoid
        version_infos = []
        for id in self.objectIds():
            repoid, version_info = self._split_id(id)
            if repoid is None:
                continue
            if rid != repoid:
                continue
            version_infos.append(version_info)
        return version_infos

    #
    # Misc
    #

    def _get_id_prefix(self, repoid):
        return '%s__' % repoid

    def _get_id(self, repoid, version_info):
        id = '%s__%04d' % (repoid, version_info)
        return id

    def _split_id(self, id):
        try:
            repoid, version_info = id.split('__')
            version_info = int(version_info)
        except ValueError:
            LOG('ObjectRepository', ERROR, 'Cannot split id %s' % id)
            return (None, None)
        return (repoid, version_info)

    #
    # Forbid any workflow
    #

    # This done later by using setattr because the id is variable
    #.cps_workflow_configuration = NoWorkflowConfiguration()

    #
    # Misc: object creation without CMF security checks
    #

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
    def constructContent(self, type_name, id, *args, **kw):
        """Construct an CMFish object without all the security checks.

        Returns the object's id.
        The object is constructed in the repository.
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
        ob._setPortalTypeName(type_name)
        ob.reindexObject(idxs=['portal_type', 'Type'])
        return id

    #
    # ZMI
    #

    manage_options = PortalFolder.manage_options


InitializeClass(ObjectRepository)


# Create a workflow configuration object that denies any workflow
setattr(ObjectRepository, CPSWorkflowConfig_id,
        NoWorkflowConfiguration())
# security.declarePrivate(...)
setattr(ObjectRepository, CPSWorkflowConfig_id+'__roles__', ())

