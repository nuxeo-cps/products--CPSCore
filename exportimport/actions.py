# (C) Copyright 2011 CPS-CMS Community <http://cps-cms.org/>
# Authors:
#     G. Racinet <gracinet@cps-cms.org>
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

"""Re-inforce purge of action providers.

CMFCore's adapter does not really purge providers, but merely deferences them.
Then in _initOldStyleActions, there's creation of DOM fragments on the fly,
hardcoded to purge=False
"""

from Products.CMFCore.utils import getToolByName
from Products.CMFCore.exportimport.actions import ActionsToolXMLAdapter

class CPSActionsToolXMLAdapter(ActionsToolXMLAdapter):

    def _purgeProviders(self):
        tool = self.context
        for provider_id in tool.listActionProviders():
            provider = getToolByName(self.context, provider_id, None)
            if provider is None:
                # could have disappeared, we'll start from scratch anyway
                continue
            actions = provider.listActions()
            if actions:
                # method expects indices in the list of actions
                provider.deleteActions(range(len(actions)))

        # now dereference
        ActionsToolXMLAdapter._purgeProviders(self)
