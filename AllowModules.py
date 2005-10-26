# (C) Copyright 2003-2005 Nuxeo SARL <http://nuxeo.com>
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

from AccessControl import allow_type, allow_class
from AccessControl import ModuleSecurityInfo

ModuleSecurityInfo('re').declarePublic('compile', 'findall',
  'match', 'search', 'split', 'sub', 'subn', 'error',
  'I', 'L', 'M', 'S', 'X')
import re
allow_type(type(re.compile('')))
allow_type(type(re.compile('x')))
allow_type(type(re.match('x', 'x')))
allow_type(type(re.sub('x', 'x', 'x')))

ModuleSecurityInfo('urllib').declarePublic('urlencode')
ModuleSecurityInfo('cgi').declarePublic('escape')
ModuleSecurityInfo('zLOG').declarePublic('LOG', 'DEBUG', 'INFO')
ModuleSecurityInfo('AccessControl').declarePublic('Unauthorized')
ModuleSecurityInfo('types').declarePublic('IntType', 'StringType',
                                          'ListType', 'DictType',
                                          'TupleType')
ModuleSecurityInfo('DateTime.DateTime').declarePublic('DateTimeError')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic('resetSessionLanguageSelection')
ModuleSecurityInfo(
    'Products.CMFCore.WorkflowCore').declarePublic('WorkflowException')

try:
    from mx import Tidy
    allow_class(Tidy)
    ModuleSecurityInfo('mx').declarePublic('Tidy')
except ImportError:
    pass

ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'KEYWORD_DOWNLOAD_FILE')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'KEYWORD_ARCHIVED_REVISION')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'KEYWORD_SWITCH_LANGUAGE')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'KEYWORD_VIEW_LANGUAGE')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'KEYWORD_VIEW_ZIP')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'SESSION_LANGUAGE_KEY')
ModuleSecurityInfo('Products.CPSCore.utils').declarePublic(
    'REQUEST_LANGUAGE_KEY')
