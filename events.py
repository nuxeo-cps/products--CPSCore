# (C) Copyright 2005 Nuxeo SAS <http://nuxeo.com>
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
"""CPS events management.
"""


"""
Note about events currently sent and their Five equivalents:

- sys_add_cmf_object
  (IObjectAddedEvent)

- sys_add_object
  IObjectAddedEvent

- sys_del_object
  IObjectWillBeRemovedEvent

- sys_modify_object
  IObjectModifiedEvent

- sys_modify_security
  IObjectModifiedEvent... ?

- sys_order_object
  IContainerModifiedEvent

- workflow_* (for each transition)
  workflow_cut_copy_paste
  workflow_delete
  workflow_modify

- modify_object

- new_trackback

- rss_channel_refresh

- user_logout

- remote_controller_publish_documents
  remote_controller_change_document_position
  remote_controller_lock_document
  remote_controller_unlock_document

- forum_new_post
  forum_new_comment
  forum_comment_published
  forum_post_published
  forum_comment_unpublished
  forum_post_unpublished
  forum_comment_rejected
  forum_post_rejected
  forum_comment_deleted
  forum_post_deleted

- calendar_event_invite
  calendar_event_deleted
  calendar_event_status_change
  calendar_event_modify

"""

from Products.CMFCore.utils import getToolByName

import zope.interface
from zope.app.event.interfaces import IObjectModifiedEvent
from zope.app.container.interfaces import IContainerModifiedEvent
from zope.app.container.interfaces import IObjectMovedEvent
from OFS.interfaces import IObjectWillBeMovedEvent

from Products.CPSCore.interfaces import ISecurityModificationDescription

from zope.app.event.objectevent import ObjectModifiedEvent


def handleObjectEvent(ob, event):
    """Backward-compatibility subscriber for recursive events.

    Redispatches events to the portal_eventservice with the old API
    based on event types which are strings.
    """
    #print 'handleObjectEvent %s %s' % (event.__class__.__name__,
    #                                   '/'.join(ob.getPhysicalPath()))
    if IObjectWillBeMovedEvent.providedBy(event):
        if event.oldParent is None:
            # IObjectWillBeAdded
            return
        event_type = 'sys_del_object'
    elif IObjectMovedEvent.providedBy(event):
        if event.newParent is None:
            # IObjectRemovedEvent
            return
        event_type = 'sys_add_object'
    elif IContainerModifiedEvent.providedBy(event):
        event_type = 'sys_order_object'
    elif IObjectModifiedEvent.providedBy(event):
        if (len(event.descriptions) == 1 and
            ISecurityModificationDescription.providedBy(event.descriptions[0])
            ):
            # don't turn a sys_modify_security into a sys_modify_object
            return
        event_type = 'sys_modify_object'
    else:
        return

    evtool = getToolByName(ob, 'portal_eventservice', None)
    if evtool is None:
        return

    evtool.notifyCompat(event_type, ob, {})


class SecurityModificationDescription(object):
    """Modification of an object's security.
    """
    zope.interface.implements(ISecurityModificationDescription)


def securityModificationEvent(ob):
    """Create an event describing a security modification.
    """
    desc = SecurityModificationDescription()
    event = ObjectModifiedEvent(ob)
    event.descriptions = (desc,)
    return event
