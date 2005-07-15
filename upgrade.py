# Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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

def upgrade_334_335_repository(context):
    """Upgrade the repository to remove security synthesis remnants.

    Removes all local roles on the contained objects.
    """
    PARTIAL_COMMIT_EVERY = 100
    repo = context.portal_url.getPortalObject().portal_repository
    count = 0
    for ob in repo.objectValues():
        changed = False
        print ob
        print getattr(ob, '__ac_local_roles__', None)
        print getattr(ob, '__ac_local_group_roles__', None)
        if getattr(ob, '__ac_local_roles__', None) is not None:
            ob.__ac_local_roles__ = None
            changed = True
        if getattr(ob, '__ac_local_group_roles__', None) is not None:
            ob.__ac_local_group_roles__ = None
            changed = True
        if changed:
            count += 1
            if (count % PARTIAL_COMMIT_EVERY) == 0:
                get_transaction().commit(1)
    return "%s repository objects cleaned" % count
