# (C) Copyright 2002 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Jalon <jj@nuxeo.com>
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

from pprint import pformat
from zLOG import LOG, INFO
from Globals import InitializeClass, DTMLFile
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import UniqueObject, SimpleItemWithProperties, \
                                   getToolByName
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens

class LoggerTool(UniqueObject, SimpleItemWithProperties):
    """Logger Tool just logs events.

    You have to register portal_logger in portal_eventservice
    so portal_logger is notifyied on any event (or just filter
    some)
    """

    id = 'portal_logger'

    meta_type = 'CPS Logger Tool'

    manage_options = (
        {
            'label': 'Test',
            'action': 'manage_logTestForm',
        },
    ) + SimpleItemWithProperties.manage_options

    security = ClassSecurityInfo()

    security.declarePrivate('notify_log')
    def notify_log(self, event_type, object, infos):
        if event_type != 'log':
            path = object.getPhysicalPath()
            path = '/'.join(path)
            title = object.title
            if title:
                title = ' (%s)' % (title, )
            s = """
-------------------------------------------------------------------
Notification of event of type %(event_type)s
Object: %(id)s%(title)s - meta_type: %(meta_type)s
Path: %(path)s
Infos:
%(infos)s"""
            s = s % {
                'event_type': event_type,
                'id': object.getId(),
                'title': title,
                'meta_type': object.meta_type,
                'path': path,
                'infos': pformat(infos),
            }
        else:
            s = """
-------------------------------------------------------------------
message: %(message)s""" % infos
        LOG('Logger', INFO, s)

    security.declareProtected(ViewManagementScreens, 'manage_logTestForm')
    manage_logTestForm = DTMLFile('zmi/logTestForm', globals())

    security.declareProtected(ViewManagementScreens, 'manage_logTest')
    def manage_logTest(self, message, REQUEST=None):
        """Logs a simple message.

        This methods uses event service's notifications.
        """
        evtool = getToolByName(self, 'portal_eventservice')
        evtool.notify('log', self, {'message': message})

    def __call__(self, message):
        """Logs a simple message.
        """
        self.manage_logTest(message)

InitializeClass(LoggerTool)
