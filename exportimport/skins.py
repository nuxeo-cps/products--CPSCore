# (C) Copyright 2012 CPS-CMS Community <http://cps-cms.org/>
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

from zope.component import adapts
from Acquisition import aq_parent, aq_inner
from Products.CMFCore.exportimport.skins import SkinsToolXMLAdapter

from Products.GenericSetup.interfaces import ISetupEnviron
from Products.CMFCore.interfaces import ISkinsTool

class InserterSkinsToolXMLAdapter(SkinsToolXMLAdapter):
    """An override to correct a bug in CMF 2.1.1

    Will be tested by CPS products that depend on CPSDefault
    """

    adapts(ISkinsTool, ISetupEnviron)

    _LOGGER_ID = 'skins'

    name = 'skins'

    def _initSkinPaths(self, node):
        """The original version cannot interpret insert-after correctly.

        the reason: the existing path layers are *appended* to the current
        XML node therefore, insert-after cannot work !
        All this code is CMF's except where marked with CPS
        """

        for child in node.childNodes:
            if child.nodeName != 'skin-path':
                continue
            path_id = str(child.getAttribute('name'))
            if str(child.getAttribute('remove')):
                self._removeSkin(skin_name=path_id)
                continue
            if path_id == '*':
                for path_id, path in self.context._getSelections().items():
                    path = self._updatePath(path, child)
                    self.context.addSkinSelection(path_id, path)
            else:
                # CPS find the first given layer node for later insertion
                for first_given in child.childNodes:
                    if first_given.nodeName == 'layer':
                        break
                else:
                    first_given = None
                # CPS end
                path = ''
                if child.hasAttribute('based-on'):
                    try:
                        basename = child.getAttribute('based-on')
                        path = self.context._getSelections()[basename]
                    except KeyError:
                        pass
                if path_id in self.context._getSelections():
                    oldpath = self.context._getSelections()[path_id].split(',')
                    for layer in oldpath:
                        if layer not in path:
                            layernode = self._doc.createElement('layer')
                            layernode.setAttribute('name', layer)
                            if oldpath.index(layer) == 0:
                                layernode.setAttribute('insert-before', '*')
                            else:
                                pos = oldpath[oldpath.index(layer)-1]
                                layernode.setAttribute('insert-after', pos)
                            child.insertBefore(layernode, first_given) # CPS
                path = self._updatePath(path, child)
                self.context.addSkinSelection(path_id, path)
        #
        # Purge and rebuild the skin path, now that we have added our stuff.
        # Don't bother if no REQUEST is present, e.g. when running unit tests
        #
        request = getattr(self.context, 'REQUEST', None)
        skinnable = aq_parent(aq_inner(self.context))
        if request is not None and skinnable is not None:
            skinnable.clearCurrentSkin()
            skinnable.setupCurrentSkin(request)

