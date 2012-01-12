# (C) Copyright 2010-2011 CPS-CMS Community <http://cps-cms.org/>
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

"""Patches of GenericSetup

Most of them are related to encoding issues
"""

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo

from Products.GenericSetup.context import BaseContext

def getEncoding(self):
    """Work around the fact that the default encoding is 'no encoding',
    leading to 'ascii' encoding, that breaks snapshots with unicode content,
    whereas the default XML encoding is utf-8
    Of course, this could be done at the level of CPS' subclass,
    but it's simpler  and safer to do it once and for all here.
    """

    enc = self._encoding
    return enc is not None and enc or 'utf-8'

BaseContext.getEncoding = getEncoding

import re
from Products.GenericSetup.utils import ExportConfiguratorBase
from Products.GenericSetup.permissions import ManagePortal

ExportConfiguratorBase.security = ClassSecurityInfo()
ExportConfiguratorBase.security.declareProtected(ManagePortal, 'generateXML')
def generateXML(self, **kw):
    """ Pseudo API.

    Patch specifics: in case the generated xml is unicode, we convert it to
    the appropriate encoding, according to its header.
    First use-case: action icons
    """
    xml = self._template(**kw)
    if isinstance(xml, unicode):
        match = re.match(r'<\?xml[^>]*?encoding="(.*?)"', xml)
        if match is None:
            enc = 'utf8' # UTF-8 is the default XML encoding
        else:
            enc = match.group(1)
        xml = xml.encode(enc)
    return xml

ExportConfiguratorBase.generateXML = generateXML

InitializeClass(ExportConfiguratorBase)
