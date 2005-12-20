# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Authors: Julien Jalon <jj@nuxeo.com>
#          Florent Guillaume <fg@nuxeo.com>
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
"""Remains of events, will go away.
"""

from Products.CPSCore.EventServiceTool import getEventService

def notify(context, event_type, object, *args, **kw):
    evtool = getEventService(context)
    infos = {'args': args, 'kw': kw}
    evtool.notify(event_type, object, infos)

#
# Generators of CMF Add events
#

from Products.CMFCore.CMFCatalogAware import CMFCatalogAware

def manage_afterCMFAdd(self, item, container):
    """Notify object and event service of CMF add finalization."""
    notify(self, 'sys_add_cmf_object', self)
    self._CMFCatalogAware__recurse('manage_afterCMFAdd', item, container)

CMFCatalogAware.manage_afterCMFAdd = manage_afterCMFAdd

