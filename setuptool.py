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
"""CPS Setup Tool.
"""

from Products.CMFCore.utils import UniqueObject
from Products.GenericSetup.tool import SetupTool


class CPSSetupTool(UniqueObject, SetupTool):
    """CPS Setup Tool.

    Compared to the GenericSetup tool, it has some upgrade capabilities
    and simpler interface.
    """

    id = 'portal_setup'
    meta_type = 'CPS Setup Tool'

    def __init__(self):
        SetupTool.__init__(self, self.id)

    def getEncoding(self):
        """See ISetupTool.
        """
        return 'iso-8859-15'
