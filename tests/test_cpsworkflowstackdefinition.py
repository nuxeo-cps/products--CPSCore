# -*- coding: iso-8859-15 -*-
import Zope
import unittest
from OFS.Folder import Folder

from Testing import ZopeTestCase
from Products.CMFCore.tests.base.testcase import SecurityRequestTest
from Products.CPSCore.CPSWorkflowStacks import SimpleStack, HierarchicalStack
from Products.CPSCore.CPSWorkflowStackDefinitions import  \
     BaseWorkflowStackDefinition, \
     SimpleWorkflowStackDefinition, \
     HierarchicalWorkflowStackDefinition

from Interface.Verify import verifyClass
from Products.CPSCore.interfaces.IWorkflowStackDefinition import \
     IWorkflowStackDefinition

#######################################################################
# Fake a User Folder with groups
#######################################################################

class FakeGroup:
    def __init__(self, users):
        self._users = users
    def getUsers(self):
        return self._users

class FakeUserFolderWithGroups:
    _groups = {'group1': FakeGroup(['user1']),
               'group2': FakeGroup(['user1', 'user2'])}
    def getGroupById(self, id):
        # KeyError if not found as PUF
        # so that we'll be able to test
        return self._groups[id]

########################################################################
# Fake a portal_membership tool
########################################################################

class FakeMember:
    def __init__(self, id, roles=()):
        self._userid = id
        self._roles = roles
    def getMemberId(self):
        return self._userid
    def getRolesInContext(self, context):
        return self._roles

class FakeMembershipTool:
    _users = {'user3' : FakeMember('user3', ('Owner', 'WorkspaceReader')),
              'user1' : FakeMember('user1', ('WorkspaceManager',)),
              'user2' : FakeMember('user1', ('WorkspaceMember',)),
             }
    _authenticated_user = _users['user3']
    def getAuthenticatedMember(self):
        return self._authenticated_user
    def getMemberById(self, member_id):
        return self._users.get(member_id)
    def isAnonymousUser(self):
        return 0

#######################################################################

class TestCPSWorkflowStackDefinition(SecurityRequestTest):

    def test_interface(self):
        verifyClass(IWorkflowStackDefinition, BaseWorkflowStackDefinition)
        verifyClass(IWorkflowStackDefinition, SimpleWorkflowStackDefinition)
        verifyClass(IWorkflowStackDefinition, HierarchicalWorkflowStackDefinition)

    def test_BaseWorkflowStackDefinition(self):
        base = BaseWorkflowStackDefinition(101,
                                           'toto',
                                           ass_local_role='WorkspaceManager')

        # Basics
        self.assertEqual(base.meta_type, 'Base Workflow Stack Definition')
        self.assertEqual(base.getStackDataStructureType(), 101)
        self.assertEqual(base.getStackWorkflowVariableId(), 'toto')
        self.assertEqual(base.getAssociatedLocalRole(), 'WorkspaceManager')

        # Not implemented methods
        self.assertRaises(NotImplementedError, base.push, None)
        self.assertRaises(NotImplementedError, base.pop, None)
        self.assertRaises(NotImplementedError, base.listLocalRoles, None)
        self.assertRaises(NotImplementedError, base.canManageStack,
                          None, None, None, None)

        # Lock / unlock
        self.assertEqual(base.isLocked(), 0)
        base.doLockStack()
        self.assertEqual(base.isLocked(), 1)
        base.doUnLockStack()
        self.assertEqual(base.isLocked(), 0)

    def test_SimpleWorkflowStackDefinition(self):
        simple = SimpleWorkflowStackDefinition(101,
                                               'toto',
                                               ass_local_role='WorkspaceManager')

        # Basics
        self.assertEqual(simple.meta_type, 'Simple Workflow Stack Definition')
        self.assertEqual(simple.getStackDataStructureType(), 101)
        self.assertEqual(simple.getStackWorkflowVariableId(), 'toto')
        self.assertEqual(simple.getAssociatedLocalRole(), 'WorkspaceManager')

        # Lock / unlock
        self.assertEqual(simple.isLocked(), 0)
        simple.doLockStack()
        self.assertEqual(simple.isLocked(), 1)
        simple.doUnLockStack()
        self.assertEqual(simple.isLocked(), 0)

        # Stack ds preparation

        # No given stack
        ds = simple._prepareStack(ds=None)
        self.assertEqual(ds.meta_type, 'Simple Stack')

        # A given SimpleStack
        sstack = SimpleStack()
        ds = simple._prepareStack(ds=sstack)
        self.assertEqual(ds.meta_type, 'Simple Stack')
        self.assertEqual(ds, sstack)

        # A wrong type given as ds
        # Will change it for a SimpleStack
        hstack = HierarchicalStack()
        ds = simple._prepareStack(ds=hstack)
        self.assertEqual(ds.meta_type, 'Simple Stack')
        self.assertNotEqual(ds, hstack)

        #
        # push
        #

        sstack = SimpleStack()

        # Push one guy in it
        new_stack = simple.push(sstack, member_ids=['user1'])

        # Not the same instance since it's a copy
        self.assertNotEqual(new_stack, sstack)

        # Check meta_type
        self.assertEqual(new_stack.meta_type, 'Simple Stack')

        # Check local roles

        # No former local roles mapping
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        self.assertEqual(simple.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceManager',)})
        # Check if the former local roles are recorded
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',)})

        # Try to remove the user1

        # get a copy of the initial stack
        self.assertNotEqual(new_stack, simple.pop(new_stack, ids=['user1']))
        self.assertEqual(new_stack.getStackContent(), [])
        self.assertEqual(new_stack.meta_type, 'Simple Stack')


        # Check if the former local roles are recorded
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',)})
        self.assertEqual(simple.listLocalRoles(new_stack),
                         {})

        # Check an empty push.
        # We get back an empty stack
        new_stack = simple.push(new_stack)
        self.assertNotEqual(new_stack, None)
        self.assertEqual(new_stack.getStackContent(), [])
        self.assertEqual(new_stack.meta_type, 'Simple Stack')

        # Local roles (current / former)
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        self.assertEqual(simple.listLocalRoles(new_stack),
                         {})

        # Push again
        new_stack = simple.push(new_stack, member_ids=['user1', 'user2'])
        self.assertNotEqual(new_stack, None)
        self.assertEqual(new_stack.meta_type, 'Simple Stack')
        self.assertEqual(new_stack.getStackContent(), ['user1', 'user2'])

        # Local Roles
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        self.assertEqual(simple.listLocalRoles(new_stack),
                         {'user1':('WorkspaceManager',),
                          'user2':('WorkspaceManager',)})
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1':('WorkspaceManager',),
                          'user2':('WorkspaceManager',)})

        # Add a fake acl_users to the instance
        aclu = FakeUserFolderWithGroups()
        # Add a fake membership tool
        mtool = FakeMembershipTool()
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user3',
                                               context=self),
                         0)
        # No id specified gonna ask the authenticated member (user3)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         0)
        # Add user3 wich is the one authenticated within the fake tool
        new_stack = simple.push(new_stack, member_ids=['user3'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)
        # Remove user1 and user2
        new_stack = simple.pop(new_stack, ids=['user1', 'user2'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # Add group group1 where user1 is a user
        new_stack = simple.push(new_stack, group_ids=['group1'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # Add a group in the stack that doesn't exist
        new_stack = simple.push(new_stack, group_ids=['group3'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # user1 and user2 defined within group2
        new_stack = simple.push(new_stack, group_ids=['group2'])
        self.assertEqual(new_stack.getStackContent(),
                         ['user3', 'group:group1', 'group:group3', 'group:group2'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # Remove group1 and group3
        new_stack = simple.pop(new_stack, ids=['group:group1', 'group:group3',])
        self.assertEqual(new_stack.getStackContent(),
                         ['user3', 'group:group2'])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # Remove group2
        # User 1 stil within the stack by himself
        new_stack = simple.pop(new_stack, ids=['group:group2'])
        self.assertEqual(new_stack.getStackContent(),
                         ['user3',])
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

        # Remove user1
        new_stack = simple.pop(new_stack, ids=['user3'])
        self.assertEqual(new_stack.getStackContent(), [])


        #
        # Here user1 is WorkspaceManager wich is the associated local roles and
        # because the stack is empty it's granted
        #

        member_user1 = mtool.getMemberById('user1')
        user1_roles = member_user1.getRolesInContext(self)
        self.assertEqual('WorkspaceManager' in user1_roles, 1)
        self.assertEqual(simple.getAssociatedLocalRole(), 'WorkspaceManager')

        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user1',
                                               context=self),
                         1)
        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)

        #
        # Here user3 is the Authenticated Member because the stack is empty
        # it's granted
        #

        auth_member = mtool.getAuthenticatedMember()
        self.assertEqual(auth_member.getMemberId(), 'user3')
        auth_roles = auth_member.getRolesInContext(self)
        self.assertEqual('Owner' in auth_roles, 1)

        self.assertEqual(simple.canManageStack(ds=new_stack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               context=self),
                         1)

    def test_HierarchicalWorkflowStackDefinitionCurrentLevel(self):
        hierarchical = HierarchicalWorkflowStackDefinition(
            101,
            'toto',
            ass_local_role='WorkspaceManager',
            up_local_role='WorkspaceReader',
            down_local_role='WorkspaceReader')

        # Basics
        self.assertEqual(hierarchical.meta_type,
                         'Hierarchical Workflow Stack Definition')
        self.assertEqual(hierarchical.getStackDataStructureType(), 101)
        self.assertEqual(hierarchical.getStackWorkflowVariableId(), 'toto')
        self.assertEqual(hierarchical.getAssociatedLocalRole(),
                         'WorkspaceManager')

        # Lock / unlock
        self.assertEqual(hierarchical.isLocked(), 0)
        hierarchical.doLockStack()
        self.assertEqual(hierarchical.isLocked(), 1)
        hierarchical.doUnLockStack()
        self.assertEqual(hierarchical.isLocked(), 0)

        # Stack ds preparation
        ds = hierarchical._prepareStack(ds=None)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')

        # A given HierarchicalStack
        hstack = HierarchicalStack()
        ds = hierarchical._prepareStack(ds=hstack)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')
        self.assertEqual(ds, hstack)

        # A wrong type given as ds
        # Will change it for a HierarchicalStack
        sstack = SimpleStack()
        ds = hierarchical._prepareStack(ds=sstack)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')
        self.assertNotEqual(ds, sstack)

        #
        # push
        #

        hstack = HierarchicalStack()

        # Push one guy in it
        new_stack = hierarchical.push(hstack,
                                      member_ids=['user1'],
                                      levels=[0])

        # Not the same instance since it's a copy
        self.assertNotEqual(new_stack, hstack)

        # Check meta_type
        self.assertEqual(new_stack.meta_type, 'Hierarchical Stack')

        # Check local roles

        # No former local roles mapping
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        # Push the guy in it
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceManager',)})
        # Check if the former local roles are recorded
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',)})

        # Try to remove the user1

        # get a copy of the initial stack
        self.assertNotEqual(new_stack, hierarchical.pop(new_stack,
                                                        ids=['0,user1',]))
        self.assertEqual(new_stack.getLevelContent(), [])
        self.assertEqual(new_stack.meta_type, 'Hierarchical Stack')
        # Check if the former local roles are recorded
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',)})
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {})

        # Check an empty push.
        # We get back an empty stack
        new_stack = hierarchical.push(new_stack)
        self.assertNotEqual(new_stack, None)
        self.assertEqual(new_stack.getLevelContent(), [])
        self.assertEqual(new_stack.meta_type, 'Hierarchical Stack')

        # Local roles (current / former)
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {})

        # Push again
        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user1', 'user2'],
                                      levels=[0,0])
        self.assertNotEqual(new_stack, None)
        self.assertEqual(new_stack.meta_type, 'Hierarchical Stack')
        self.assertEqual(new_stack.getLevelContent(), ['user1', 'user2'])

        # Local Roles
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1':('WorkspaceManager',),
                          'user2':('WorkspaceManager',)})
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1':('WorkspaceManager',),
                          'user2':('WorkspaceManager',)})

        # Add a fake acl_users to the instance
        aclu = FakeUserFolderWithGroups()
        # Add a fake membership tool
        mtool = FakeMembershipTool()
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user3',
                                                     context=self),
                         0)
        # No id specified gonna ask the authenticated member (user3)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         0)
        # Add user3 wich is the one authenticated within the fake tool
        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user3'],
                                      levels=[0])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)
        # Remove user1 and user2
        new_stack = hierarchical.pop(new_stack,
                                     ids=['0,user1', '0,user2'])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # Add group group1 where user1 is a user
        new_stack = hierarchical.push(new_stack,
                                      group_ids=['group1'],
                                      levels=[0])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # Add a group in the tack that doesn't exist
        new_stack = hierarchical.push(new_stack,
                                      group_ids=['group3'],
                                      levels=[0])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # user1 and user2 defined within group2
        new_stack = hierarchical.push(new_stack,
                                      group_ids=['group2'],
                                      levels=[0])
        self.assertEqual(new_stack.getLevelContent(),
                         ['user3', 'group:group1', 'group:group3', 'group:group2'])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # Remove group1 and group3
        new_stack = hierarchical.pop(new_stack,
                                     ids=['0,group:group1', '0,group:group3',])
        self.assertEqual(new_stack.getLevelContent(),
                         ['user3', 'group:group2'])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         1)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # Remove group2
        # User 1 stil within the stack by himself
        new_stack = hierarchical.pop(new_stack,
                                     ids=['0,group:group2'])
        self.assertEqual(new_stack.getLevelContent(),
                         ['user3',])
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)
        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

        # Remove user1
        new_stack = hierarchical.pop(new_stack,
                                     ids=['0,user3'])
        self.assertEqual(new_stack.getLevelContent(), [])

        #
        # Here user1 is WorkspaceManager wich is the associated local roles and
        # because the stack is empty it's granted
        #

        member_user1 = mtool.getMemberById('user1')
        user1_roles = member_user1.getRolesInContext(self)
        self.assertEqual('WorkspaceManager' in user1_roles, 1)
        self.assertEqual(hierarchical.getAssociatedLocalRole(), 'WorkspaceManager')

        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)

        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)

        #
        # Here user3 is the Authenticated Member because the stack is empty
        # it's granted
        #

        auth_member = mtool.getAuthenticatedMember()
        self.assertEqual(auth_member.getMemberId(), 'user3')
        auth_roles = auth_member.getRolesInContext(self)
        self.assertEqual('Owner' in auth_roles, 1)

        self.assertEqual(hierarchical.canManageStack(ds=new_stack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     context=self),
                         1)

    def test_HierarchicalWorkflowStackDefinitionWithLevelChanges(self):

        # Add a fake acl_users to the instance
        aclu = FakeUserFolderWithGroups()
        # Add a fake membership tool
        mtool = FakeMembershipTool()

        hierarchical = HierarchicalWorkflowStackDefinition(
            101,
            'toto',
            ass_local_role='WorkspaceManager',
            up_ass_local_role='WorkspaceMember',
            down_ass_local_role='WorkspaceReader')

        # Basics
        self.assertEqual(hierarchical.meta_type,
                         'Hierarchical Workflow Stack Definition')
        self.assertEqual(hierarchical.getStackDataStructureType(), 101)
        self.assertEqual(hierarchical.getStackWorkflowVariableId(), 'toto')
        self.assertEqual(hierarchical.getAssociatedLocalRole(),
                         'WorkspaceManager')

        # Lock / unlock
        self.assertEqual(hierarchical.isLocked(), 0)
        hierarchical.doLockStack()
        self.assertEqual(hierarchical.isLocked(), 1)
        hierarchical.doUnLockStack()
        self.assertEqual(hierarchical.isLocked(), 0)

        # Stack ds preparation
        ds = hierarchical._prepareStack(ds=None)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')

        # A given HierarchicalStack
        hstack = HierarchicalStack()
        ds = hierarchical._prepareStack(ds=hstack)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')
        self.assertEqual(ds, hstack)

        # A wrong type given as ds
        # Will change it for a HierarchicalStack
        sstack = SimpleStack()
        ds = hierarchical._prepareStack(ds=sstack)
        self.assertEqual(ds.meta_type, 'Hierarchical Stack')
        self.assertNotEqual(ds, sstack)

        #
        # push
        #

        hstack = HierarchicalStack()

        # Push one guy in it
        new_stack = hierarchical.push(hstack,
                                      member_ids=['user1'],
                                      levels=[0])

        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user2'],
                                      levels=[0])

        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user3'],
                                      levels=[1])

        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user4'],
                                      levels=[-1])

        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user5'],
                                      levels=[2])

        new_stack = hierarchical.push(new_stack,
                                      member_ids=['user6'],
                                      levels=[-2])

        # Not the same instance since it's a copy
        self.assertNotEqual(new_stack, hstack)

        # Check meta_type
        self.assertEqual(new_stack.meta_type, 'Hierarchical Stack')

        ## Check local roles

        # No former local roles mapping
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {})
        # Push the guy in it
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceManager',),
                          'user2': ('WorkspaceManager',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check if the former local roles are recorded
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',),
                          'user2': ('WorkspaceManager',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        #
        # Check canManageStack for this guys
        #

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)

        #
        # Change current level to -1
        #

        hierarchical.doDecLevel(new_stack)

        # Local roles

        # Check if the former local roles
        self.assertEqual(new_stack.getFormerLocalRolesMapping(),
                         {'user1': ('WorkspaceManager',),
                          'user2': ('WorkspaceManager',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # current ones
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceManager',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # they are now recorded
        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceManager',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)


        #
        # Change current level to -2
        #

        hierarchical.doDecLevel(new_stack)

        # current ones
        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceManager',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Current Local roles mapping
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceReader',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceManager',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         1)


        #
        # Change current level to -1
        #

        hierarchical.doIncLevel(new_stack)

        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceReader',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceManager',),
                          })

        # Current Local roles mapping
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceManager',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)


        #
        # Change current level to 0
        #

        hierarchical.doIncLevel(new_stack)

        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceReader',),
                          'user2': ('WorkspaceReader',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceManager',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Current Local roles mapping
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceManager',),
                          'user2': ('WorkspaceManager',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)


        #
        # Change current level to 1
        #

        hierarchical.doIncLevel(new_stack)

        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceManager',),
                          'user2': ('WorkspaceManager',),
                          'user3': ('WorkspaceReader',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Current Local roles mapping
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceMember',),
                          'user2': ('WorkspaceMember',),
                          'user3': ('WorkspaceManager',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)

        #
        # Change current level to 2
        #

        hierarchical.doIncLevel(new_stack)

        self.assertEqual(hierarchical.getFormerLocalRolesMapping(new_stack),
                         {'user1': ('WorkspaceMember',),
                          'user2': ('WorkspaceMember',),
                          'user3': ('WorkspaceManager',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceReader',),
                          'user6': ('WorkspaceMember',),
                          })

        # Current Local roles mapping
        self.assertEqual(hierarchical.listLocalRoles(new_stack),
                         {'user1': ('WorkspaceMember',),
                          'user2': ('WorkspaceMember',),
                          'user3': ('WorkspaceMember',),
                          'user4': ('WorkspaceMember',),
                          'user5': ('WorkspaceManager',),
                          'user6': ('WorkspaceMember',),
                          })

        # Check canManageStack for this guys

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user1'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user2'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user3'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user4'}
                                                     ),
                         0)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user5'}
                                                     ),
                         1)

        self.assertEqual(hierarchical.canManageStack(new_stack,
                                                     aclu,
                                                     mtool,
                                                     self,
                                                     **{'member_id': 'user6'}
                                                     ),
                         0)

    def test_reset_simple_sdef(self):

        #
        # Test reset simple sdef
        #

        simple = SimpleWorkflowStackDefinition(
            101,
            'toto',
            ass_local_role='WorkspaceManager')

        stack = simple.push(None, member_ids=['user1'])
        self.assertEqual(stack.getMetaType(),
                         'Simple Stack')
        self.assertEqual(stack.getStackContent(),
                         ['user1'])
        stack = simple.resetStack(stack)
        self.assertEqual(stack.getMetaType(),
                         'Simple Stack')
        self.assertEqual(stack.getStackContent(),
                         [])

    def test_reset_hierarchical_sdef(self):

        #
        # Test reset simple sdef
        #

        hierarchical = HierarchicalWorkflowStackDefinition(
            101,
            'toto',
            ass_local_role='WorkspaceManager',
            up_local_role='WorkspaceReader',
            down_local_role='WorkspaceReader')

        stack = hierarchical.push(None,
                                  member_ids=['user1'],
                                  levels=[0])
        self.assertEqual(stack.getMetaType(),
                         'Hierarchical Stack')
        self.assertEqual(stack.getLevelContent(),
                         ['user1'])
        stack = hierarchical.resetStack(stack)
        self.assertEqual(stack.getMetaType(),
                         'Hierarchical Stack')
        self.assertEqual(stack.getLevelContent(),
                         [])


    def test_stack_managers(self):

        # Add a fake acl_users to the instance
        aclu = FakeUserFolderWithGroups()
        # Add a fake membership tool
        mtool = FakeMembershipTool()

        # simple stack with hierarchical stack manager id
        simple = SimpleWorkflowStackDefinition(
            101,
            'simple',
            ass_local_role='WorkspaceReader',
            manager_stack_ids=['hierarchical'])

        sstack = SimpleStack()
        #
        # Here user3 is the Authenticated Member and because the stack is empty
        # it's granted
        #
        self.assertEqual(simple.canManageStack(ds=sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user3',
                                               context=self),
                         1)
        #
        # Here user2 is nothing
        #
        self.assertEqual(simple.canManageStack(ds=sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         0)
        # push user2
        new_sstack = simple.push(sstack, member_ids=['user2'])
        self.assertEquals(new_sstack.getSize(), 1)
        # user3 cannot manage the stack anymore because it's not empty
        self.assertEqual(simple.canManageStack(ds=new_sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user3',
                                               context=self),
                         0)
        # user2 can manage the stack because he's in it
        self.assertEqual(simple.canManageStack(ds=new_sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         1)


        hierarchical = HierarchicalWorkflowStackDefinition(
            101,
            'hierarchical',
            ass_local_role='WorkspaceManager',
            up_local_role='WorkspaceReader',
            down_local_role='WorkspaceReader')

        hstack = HierarchicalStack()
        #
        # Here user1 is WorkspaceManager wich is the associated local roles and
        # because the stack is empty it's granted
        #
        self.assertEqual(hierarchical.canManageStack(ds=hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         1)
        #
        # Here user3 is the Authenticated Member and because the stack is empty
        # it's granted
        #
        self.assertEqual(hierarchical.canManageStack(ds=hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user3',
                                                     context=self),
                         1)
        #
        # Here user2 is nothing
        #
        self.assertEqual(hierarchical.canManageStack(ds=hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         0)
        # push user2
        new_hstack = hierarchical.push(hstack, member_ids=['user2'], levels=[0])
        self.assertEquals(new_hstack.getSize(), 1)
        # user1 cannot manage the stack anymore because the stack is not empty
        # anymore
        self.assertEqual(hierarchical.canManageStack(ds=new_hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user1',
                                                     context=self),
                         0)
        # user3 cannot manage the stack anymore because the stack is not empty
        # anymore
        self.assertEqual(hierarchical.canManageStack(ds=new_hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user3',
                                                     context=self),
                         0)
        # user2 can manage the stack because he's in it
        self.assertEqual(hierarchical.canManageStack(ds=new_hstack,
                                                     aclu=aclu,
                                                     mtool=mtool,
                                                     member_id='user2',
                                                     context=self),
                         1)

        #
        # Empty simple stack, and verify that user2, in hierarchical stack and
        # at current level, can manage simple stack
        #
        new_sstack = simple.pop(new_sstack, ids=['user2'])
        self.assertEqual(new_sstack.getSize(), 0)
        # user3 can manage the stack because he's authenticated and because the
        # stack is empty
        self.assertEqual(simple.canManageStack(ds=new_sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user3',
                                               context=self),
                         1)
        # user2 can manage the stack because he's in the hierarchical stack,
        # and because the simple stack has the hierarchical stack in its
        # manager stack ids
        self.assertEqual(simple.canManageStack(ds=new_sstack,
                                               aclu=aclu,
                                               mtool=mtool,
                                               member_id='user2',
                                               context=self),
                         1)


def test_suite():
    loader = unittest.TestLoader()
    return loader.loadTestsFromTestCase(TestCPSWorkflowStackDefinition)

if __name__=='__main__':
    unittest.TextTestRunner().run(test_suite())
