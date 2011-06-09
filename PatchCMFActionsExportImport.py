# (C) Copyright 2010 CPS-CMS Community <http://cps-cms.org/>
# Authors:
#     G. Racinet <georges@racinet.fr>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Fixes UTF-8 export/import for actions.

This patch is a lesser evil, and is most probably to be removed once CMF is
updated to a more recent version. Event with the current version, our actions
import step is a BBB one.

Notably, one must remark that the ZMI encoding is hardoded to UTF-8 while here
we can use the standard method to get the encoding (possibly allowing for
different encodings)

We could also register a different adapter rather than a patch, but we have
already lots of patches, the benefit is anecdotical, while a patch is consistent
with previous practice.
"""

from Products.CMFCore.utils import getToolByName

from Products.CMFCore.exportimport.actions import ActionsToolXMLAdapter


def _initOldstyleActions(self, node):
    # BBB: for CMF 1.5 profiles
    provider_id = str(node.getAttribute('name'))
    if not provider_id:
        provider_id = str(node.getAttribute('id'))
    provider = getToolByName(self.context, provider_id)
    for child in node.childNodes:
        if child.nodeName != 'action':
            continue

        action_id = str(child.getAttribute('action_id'))
        # GR change is here
        title = child.getAttribute('title')
        if isinstance(title, unicode):
            title = title.encode('utf-8')
        elif not isinstance(title, str):
            title = str(title)
        url_expr = str(child.getAttribute('url_expr'))
        condition_expr = str(child.getAttribute('condition_expr'))
        category = str(child.getAttribute('category'))
        visible = str(child.getAttribute('visible'))
        if visible.lower() == 'true':
            visible = 1
        else:
            visible = 0

        permission = ''
        for permNode in child.childNodes:
            if permNode.nodeName == 'permission':
                for textNode in permNode.childNodes:
                    if textNode.nodeName != '#text' or \
                           not textNode.nodeValue.strip():
                        continue
                    permission = str(textNode.nodeValue)
                    break  # only one permission is allowed
                if permission:
                    break

        # Remove previous action with same id and category.
        old = [i for (i, action) in enumerate(provider.listActions())
               if action.id == action_id and action.category == category]
        if old:
            provider.deleteActions(old)

        provider.addAction(action_id, title, url_expr,
                           condition_expr, permission,
                           category, visible)

ActionsToolXMLAdapter._initOldstyleActions = _initOldstyleActions
