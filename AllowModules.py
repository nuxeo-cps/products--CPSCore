# (C) Copyright 2003 Nuxeo SARL <http://nuxeo.com>
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
"""
Allow standard modules to be imported from restricted code.
"""
# (see lib/python/Products/PythonScripts/module_access_example.py)

from AccessControl import allow_type # allow_module, allow_class
from AccessControl import ModuleSecurityInfo

ModuleSecurityInfo('re').declarePublic('compile', 'findall',
  'match', 'search', 'split', 'sub', 'subn', 'error',
  'I', 'L', 'M', 'S', 'X')
import re
allow_type(type(re.compile('')))
allow_type(type(re.match('x','x')))


ModuleSecurityInfo('urllib').declarePublic('urlencode')
