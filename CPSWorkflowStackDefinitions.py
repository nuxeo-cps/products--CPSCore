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

"""CPS Workflow Stack Definitions

This module contains all CPS Stack definitions
"""

from zLOG import LOG, DEBUG

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from OFS.SimpleItem import SimpleItem

from Products.CMFCore.CMFCorePermissions import View, ModifyPortalContent

from Products.CPSCore.CPSWorkflowStacks import SimpleStack, HierarchicalStack
from Products.CPSCore.interfaces.IWorkflowStackDefinition import \
     IWorkflowStackDefinition

class BaseWorkflowStackDefinition(SimpleItem):
    """BaseWorkflowStackConfiguration

    Holds the basis configuration for a stack
    """

    meta_type = 'Base Workflow Stack Definition'

    __implements__ = IWorkflowStackDefinition

    security = ClassSecurityInfo()

    def __init__(self,
                 stack_ds_type,
                 wf_var_id,
                 **kw
                 ):
        """Constructor

        stack_ds_type   : Data Structure type holding the deleggatees
        wf_var_id       : Workflow variable holding the ds instance
        ass_local_role  : Local role assigned to members of the DS
        """
        self.stack_ds_type = stack_ds_type
        self.wf_var_id = wf_var_id

        for k, v in kw.items():
            setattr(self, k, v)

        #
        # This information has to be on the stackdef since the data structure
        # doesn't need to care about that
        #

        self._isLocked = 0

    security.declareProtected(View, 'getStackDataStructureType')
    def getStackDataStructureType(self):
        """Returns the id of the stack data structure the stack definition is
        hodling
        """
        return self.stack_ds_type

    security.declareProtected(View, 'getStackDataStructureType')
    def getStackWorkflowVariableId(self):
        """Returns the workflow variable id mapping this configuration
        """
        return self.wf_var_id

    security.declareProtected(View, 'getAssociatedLocalRole')
    def getAssociatedLocalRole(self):
        """Returns the workflow variable id mapping this configuration
        """
        return self.ass_local_role

    security.declareProtected(View, 'getGrantedLocalRole')
    def getGrantedLocalRolesForManage(self):
        """Returns the local roles granted to manage the stack.
        It's in use when the
        """
        raise NotImplementedError

    security.declareProtected(View, 'isLocked')
    def isLocked(self):
        """Is the stack locked
        """
        return self._isLocked

    security.declareProtected(ModifyPortalContent, 'doLockStack')
    def doLockStack(self):
        """Lock the stack
        """
        self._isLocked = 1

    security.declareProtected(ModifyPortalContent, 'doUnLockStack')
    def doUnLockStack(self):
        """UnLock stack
        """
        self._isLocked = 0

    security.declareProtected(ModifyPortalContent, 'push')
    def push(self, ds, **kw):
        """Push delegatees

        This method has to be implemented by a child class
        """
        raise NotImplementedError

    security.declareProtected(ModifyPortalContent, 'pop')
    def pop(self, ds, **kw):
        """Pop delegatees

        This method has to be implemented by a child class
        """
        raise NotImplementedError

    security.declareProtected(View, 'listLocalRoles')
    def listLocalRoles(self, ds):
        """Give the local roles mapping for the member / group ids within the
        stack
        """
        raise NotImplementedError

    security.declareProtected(View, 'getFormerLocalRolesMapping')
    def getFormerLocalRolesMapping(self, ds):
        """Give the former local roles mapping for the member / group ids
        within the stack
        """
        raise NotImplementedError

    security.declarePublic('canManageStack')
    def canManageStack(self, ds, aclu, mtool, context, **kw):
        """Can the current member manage the stack ?

        It will depend on the stack data structure.  We need the acl_users in
        use and the member_ship tool since I don't want to explicit acquicition
        in here
        """
        raise NotImplementedError

    security.declarePublic('getManagerStackIds')
    def getManagerStackIds(self):
        """Returns the ids of other stacks for which the people within those
        can manage this stack. For instance in the common use case members
        within the 'Pilots' stack can manage 'Associates' and 'Watchers'
        stacks.
        """
        raise NotImplementedError

    security.declarePrivate('_prepareStack')
    def _prepareStack(self, ds):
        """Prepare stack on wich we gonna work one

        ds is the data structure holding the delegatees
        """
        raise NotImplementedError

    security.declareProtected(ModifyPortalContent, 'resetStack')
    def resetStack(self, ds, **kw):
        """Reset stack contained within ds.
        """
        ds = self._prepareStack(ds)
        ds.reset()
        return ds

InitializeClass(BaseWorkflowStackDefinition)

####################################################
####################################################

class SimpleWorkflowStackDefinition(BaseWorkflowStackDefinition):
    """Simple Workflow Stack Definition
    """

    meta_type = 'Simple Workflow Stack Definition'

    security = ClassSecurityInfo()

    __implements__ = (IWorkflowStackDefinition,)

    def __init__(self,
                 stack_ds_type,
                 wf_var_id,
                 **kw
                 ):
        """Constructor

        stack_ds_type   : Data Structure type holding the deleggatees
        wf_var_id       : Workflow variable holding the ds instance
        ass_local_role  : Local role assigned to members of the DS

        The constructor will create an instance of SimpleStack to hold
        delegatees in here
        """

        BaseWorkflowStackDefinition.__init__(self,
                                             stack_ds_type,
                                             wf_var_id,
                                             **kw)

    def _prepareStack(self, ds):
        """Prepare stack on wich we gonna work one

        ds is the data structure holding the delegatees
        """
        LOG("_prepareStack()", DEBUG, 'Simple Stack')
        if ds is not None:
            if ds.meta_type != 'Simple Stack':
                ds = None
        if ds is None:
            ds = SimpleStack()
        return ds

    security.declareProtected(ModifyPortalContent, 'push')
    def push(self, ds, **kw):
        """Push delegatees

        This method has to be implemented by a child class
        """
        LOG("::SimpleWorkflowStackDefinition.push()::",
            DEBUG,
            str(kw))

        #
        # Prepare stack.
        # ds comes usually from the status
        # It might be None of not yet initialized
        #

        ds = self._prepareStack(ds)

        #
        # First extract the needed information
        # No level information is needed in here
        #

        member_ids = kw.get('member_ids', ())
        group_ids  = kw.get('group_ids',  ())

        if not (member_ids or group_ids):
            return ds

        #
        # Push members / groups
        # groups gota prefixed id  'group:'
        #

        for member_id in member_ids:
            ds.push(member_id)
        for group_id in group_ids:
            prefixed_group_id = 'group:'+group_id
            ds.push(prefixed_group_id)

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declareProtected(ModifyPortalContent, 'pop')
    def pop(self, ds, **kw):
        """pop delegatees
        """

        LOG("::SimpleWorkflowStackDefinition.pop()::",
            DEBUG,
            str(kw))

        #
        # Prepare stack.
        # ds comes usually from the status
        # It might be None of not yet initialized
        #

        ds = self._prepareStack(ds)

        #
        # Pop member / group given ids
        #

        ids = kw.get('ids', ())

        if not ids:
            return ds

        for id in ids:
            ds.removeElement(id)

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declareProtected(View, 'listLocalRoles')
    def listLocalRoles(self, ds):
        """Give the local roles mapping for the member / group ids within the
        stack

        Simple case : all the member of the stack have the associated local
        role
        """

        mapping = {}

        # Prepare the ds
        ds = self._prepareStack(ds)

        # Get stack elements
        elements = ds.getStackContent()

        #
        # Build the local role mapping Have to respect the fact that some
        # stacks might have be able to define different local roles for the
        # same element in the stack at a given time
        #

        for each in elements:
            new = mapping.get(each, ()) + (self.getAssociatedLocalRole(),)
            mapping[each] = new

        #
        # Put the information within the ds
        #

        ds.setFormerLocalRolesMapping(mapping)
        return mapping

    security.declareProtected(View, 'getFormerLocalRolesMapping')
    def getFormerLocalRolesMapping(self, ds):
        """Give the former local roles mapping for the member / group ids
        within the stack
        """
        ds = self._prepareStack(ds)
        return ds.getFormerLocalRolesMapping()

    security.declarePublic('canManageStack')
    def canManageStack(self, ds, aclu, mtool, context, **kw):
        """Check if the current authenticated member scan manage stack

        Simple case in here. If a user is in the stack it can manage it we need
        the acl_users in use and the member_ship tool since I don't want to
        explicit acquicition in here

        We need the context if the case is not yet intialized
        """

        if mtool.isAnonymousUser():
            return 0

        # prepare the ds
        ds = self._prepareStack(ds)

        #
        # Cope with member id.
        # It can be passed within th kw (member_id)
        #

        member_id = kw.get('member_id')
        if member_id is None:
            member = mtool.getAuthenticatedMember()
            member_id = member.getMemberId()
        else:
            member = mtool.getMemberById(member_id)

        #
        # Check first if the member is granted because of irts position within
        # the stack content
        #

        for each in ds.getStackContent():
            if not each.startswith('group:'):
                if each == member_id:
                    return 1
            else:
                try:
                    group_no_prefix = each[len('group:'):]
                    group = aclu.getGroupById(group_no_prefix)
                    group_users = group.getUsers()
                    if member_id in group_users:
                        return 1
                except KeyError:
                    # Group has probably been removed
                    pass

        #
        # Now let's cope with the first case when the stack is not et
        # intialized. We will grant the 'Owner' of the document and the people
        # having the same local role as the associated local roles of the stack
        #

        _granted_local_roles = ('Owner',
                                self.getAssociatedLocalRole())

        if ds.getStackContent() == []:
            if context is not None:
                member_roles = member.getRolesInContext(context)
                for lc in _granted_local_roles:
                    if lc in member_roles:
                        return 1

        return 0

    def getManagerStackIds(self):
        """Returns the ids of other stacks for which the people within those
        can manage this stack. For instance in the common use case members
        within the 'Pilots' stack can manage 'Associates' and 'Watchers'
        stacks.
        """
        return getattr(self, 'manager_stack_ids', [])

InitializeClass(SimpleWorkflowStackDefinition)

###################################################
###################################################

class HierarchicalWorkflowStackDefinition(BaseWorkflowStackDefinition):
    """Hierarchical Workflow Stack Definition
    """

    meta_type = 'Hierarchical Workflow Stack Definition'

    security = ClassSecurityInfo()

    def __init__(self,
                 stack_ds_type,
                 wf_var_id,
                 **kw
                 ):
        """Constructor

        stack_ds_type   : Data Structure type holding the deleggatees
        wf_var_id       : Workflow variable holding the ds instance
        ass_local_role : Local role assigned to members of the DS at current
        level
        up_ass_local_role : Local role assigned to members of the DS above the
        current level
        down_ass_local_role : Local role assigned to members of the DS below
        the current level

        The constructor will create an instance of HierarchicalStack to hold
        delegatees in here
        """

        __implements__ = (IWorkflowStackDefinition,)

        BaseWorkflowStackDefinition.__init__(self,
                                             stack_ds_type,
                                             wf_var_id,
                                             **kw)
    def _prepareStack(self, ds):
        """Prepare stack on wich we gonna work one

        ds is the data structure holding the delegatees
        """
        LOG("_prepareStack()", DEBUG, 'Hierarchical Stack')
        if ds is not None:
            if ds.meta_type != 'Hierarchical Stack':
                ds = None
        if ds is None:
            ds = HierarchicalStack()
        return ds

    security.declareProtected(ModifyPortalContent, 'push')
    def push(self, ds, **kw):
        """Push delegatees

        This method has to be implemented by a child class
        """
        LOG("::HierarchicalStackDefinition.push()::",
            DEBUG,
            str(kw))

        #
        # First extract the needed information
        # No level information is needed in here
        #

        member_ids = kw.get('member_ids', ())
        group_ids  = kw.get('group_ids',  ())
        levels = kw.get('levels', ())

        if not ((member_ids or group_ids) and levels):
            return ds

        #
        # Prepare stack.
        # ds comes usually from the status
        # It might be None of not yet initialized
        #

        ds = self._prepareStack(ds)

        #
        # Push members / groups
        # groups gota prefixed id  'group:'
        #

        i = 0
        for member_id in member_ids:
            try:
                ds.push(member_id, int(levels[i]))
                i += 1
            except IndexError:
                # wrong user input
                pass
        i = 0
        for group_id in group_ids:
            prefixed_group_id = 'group:'+group_id
            try:
                ds.push(prefixed_group_id, int(levels[i]))
                i += 1
            except IndexError:
                # wrong user input
                pass

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declareProtected(ModifyPortalContent, 'pop')
    def pop(self, ds, **kw):
        """pop delegatees
        """

        LOG("::SimpleWorkflowStackDefinition.pop()::",
            DEBUG,
            str(kw))

        #
        # Check arguments in here.
        # Might be wrongly called
        #

        ids = kw.get('ids', ())
        if not ids:
            return ds

        #
        # Prepare stack.
        # ds comes usually from the status
        # It might be None of not yet initialized
        #

        ds = self._prepareStack(ds)

        #
        # Pop member / group given ids
        #

        for id in ids:
            level = int(id.split(',')[0])
            the_id = id.split(',')[1]
            ds.removeElement(the_id, int(level))

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declarePublic('canManageStack')
    def canManageStack(self, ds, aclu, mtool, context, **kw):
        """Check if the current authenticated member scan manage stack

        Here, only the people at the current level are allowed to manage the
        stack. We need the acl_users in use and the member_ship tool since I
        don't want to explicit acquicition in here

        context is needed when the stack has just been initialized.
        """

        if mtool.isAnonymousUser():
            return 0

        # prepare the ds
        ds = self._prepareStack(ds)

        #
        # Cope with member id.
        # It can be passed within th kw (member_id)
        #

        member_id = kw.get('member_id')
        if member_id is None:
            member = mtool.getAuthenticatedMember()
            member_id = member.getMemberId()
        else:
            member = mtool.getMemberById(member_id)

        #
        # Check first if the member is granted because of irts position within
        # the stack content
        #

        for each in ds.getLevelContent():
            if not each.startswith('group:'):
                if each == member_id:
                    return 1
            else:
                try:
                    group_no_prefix = each[len('group:'):]
                    group = aclu.getGroupById(group_no_prefix)
                    group_users = group.getUsers()
                    if member_id in group_users:
                        return 1
                except KeyError:
                    # Group has probably been removed
                    pass

        #
        # Now let's cope with the first case when the stack is not et
        # intialized. We will grant the 'Owner' of the document and the people
        # having the same local role as the associated local roles of the stack
        #

        _granted_local_roles = ('Owner',
                                self.getAssociatedLocalRole())

        if ds.getLevelContent() == []:
            if context is not None:
                member_roles = member.getRolesInContext(context)
                for lc in _granted_local_roles:
                    if lc in member_roles:
                        return 1

        return 0

    security.declareProtected(View, 'listLocalRoles')
    def listLocalRoles(self, ds):
        """Give the local roles mapping for the member / group ids within the
        stack

        Here, we decide that only the people at the current level do have the
        main associated Local role. The other ones have a default role for
        being able to still work but they can't manage the workflow

        The people above get the up_ass_local_role
        The people below get the down_ass_local_role
        """

        mapping = {}

        # Prepare the ds
        ds = self._prepareStack(ds)
        current_level = ds.getCurrentLevel()

        #
        # Cope with people above the current level
        # Means the people at levels -1, -2, ... -n
        # Above is a sort of view of my brain ;)
        #

        above_levels = [level for level in ds.getAllLevels()
                        if level < current_level]

        for each in above_levels:
            for elt in ds.getLevelContent(level=each):
                new = mapping.get(elt, ()) + (self.up_ass_local_role,)
                mapping[elt] = new

        #
        # Cope with people below the current level
        # Means the people at levels 1, 2, ... n
        # Below is a sort of view of my brain ;)
        #

        below_levels = [level for level in ds.getAllLevels()
                        if level > current_level]

        for each in below_levels:
            for elt in ds.getLevelContent(level=each):
                new = mapping.get(elt, ()) + (self.down_ass_local_role,)
                mapping[elt] = new

        #
        # Cope with people at current level
        # They will get the ass_local_role
        #

        elements = ds.getLevelContent()
        for each in elements:
            new = mapping.get(each, ()) + (self.getAssociatedLocalRole(),)
            mapping[each] = new

        #
        # Put the information within the ds
        #

        ds.setFormerLocalRolesMapping(mapping)
        return mapping

    security.declareProtected(View, 'getFormerLocalRolesMapping')
    def getFormerLocalRolesMapping(self, ds):
        """Give the former local roles mapping for the member / group ids
        within the stack
        """
        ds = self._prepareStack(ds)
        return ds.getFormerLocalRolesMapping()

    security.declareProtected(ModifyPortalContent, 'doIncLevel')
    def doIncLevel(self, ds):
        """Increase the stack level
        """

        # Prepare the ds
        ds = self._prepareStack(ds)

        # Increase level
        ds.doIncLevel()

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declareProtected(ModifyPortalContent, 'doDecLevel')
    def doDecLevel(self, ds):
        """Decrease the stack level
        """

        # Prepare the ds
        ds = self._prepareStack(ds)

        # Decrease level
        ds.doDecLevel()

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    security.declareProtected(ModifyPortalContent, 'doDecLevel')
    def doReturnedUpDirection(self, ds):
        """Returned up the direction
        """

        # Prepare the ds
        ds = self._prepareStack(ds)

        # Inverse direction
        ds.returnUpDirection()

        #
        # For the workflow history.
        # Let's do a copy of the stack instance
        #

        ds = ds.getCopy()
        return ds

    def getManagerStackIds(self):
        """Returns the ids of other stacks for which the people within those
        can manage this stack. For instance in the common use case members
        within the 'Pilots' stack can manage 'Associates' and 'Watchers'
        stacks.
        """
        return getattr(self, 'manager_stack_ids', [])

InitializeClass(HierarchicalWorkflowStackDefinition)
