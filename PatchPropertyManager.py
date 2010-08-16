# Copyright (C) 2006 Nuxeo SAS <http://nuxeo.com>
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
# $Id: unicodepatches.py 48546 2006-08-24 10:00:26Z fguillaume $
"""Patches to have things work ok in unicode.
"""

from Products.GenericSetup.utils import PropertyManagerHelpers
from Products.GenericSetup.exceptions import BadRequest

from cgi import escape
from OFS.PropertyManager import PropertyManager
from ZPublisher.Converters import type_converters

def asciify(value):
    """Convert a unicode string to pure ascii str if possible.

    This is because lots of code still expect pure ascii strings.
    """
    try:
        value = value.encode('ascii')
    except UnicodeError:
        pass
    return value

if True: # keep indentation

    def _initProperties(self, node):
        obj = self.context
        if node.hasAttribute('i18n:domain'):
            i18n_domain = str(node.getAttribute('i18n:domain'))
            obj._updateProperty('i18n_domain', i18n_domain)

        prop_dict = obj.propdict()

        # #2211: upgrading existing properties
        to_add = []
        for p in obj.__class__._properties:
            pid = p['id']
            if pid not in prop_dict:
                # typically, some prop has been added to object at a time when
                # definition at class level didn't include this prop
                to_add.append(p)
                prop_dict[pid] = p # will be useful later (PERF comment below)

        if to_add:
            obj._properties = obj._properties + tuple(to_add)

        for child in node.childNodes:
            if child.nodeName != 'property':
                continue
            prop_id = str(child.getAttribute('name'))
            # GR PERF: costly propdict() is evaluated for each prop
            prop_map = obj.propdict().get(prop_id, None)

            if prop_map is None:
                if child.hasAttribute('type'):
                    val = child.getAttribute('select_variable')
                    obj._setProperty(prop_id, val, child.getAttribute('type'))
                    prop_map = obj.propdict().get(prop_id, None)
                else:
                    raise ValueError("undefined property '%s'" % prop_id)

            if not 'w' in prop_map.get('mode', 'wd'):
                raise BadRequest('%s cannot be changed' % prop_id)

            elements = []
            for sub in child.childNodes:
                if sub.nodeName == 'element':
                    elements.append(asciify(sub.getAttribute('value')))

            if elements or prop_map.get('type') == 'multiple selection':
                prop_value = tuple(elements) or ()
            elif prop_map.get('type') == 'boolean':
                prop_value = self._convertToBoolean(self._getNodeText(child))
            else:
                # if we pass a *string* to _updateProperty, all other values
                # are converted to the right type
                prop_value = asciify(self._getNodeText(child))

            if not self._convertToBoolean(child.getAttribute('purge')
                                          or 'True'):
                # If the purge attribute is False, merge sequences
                prop = obj.getProperty(prop_id)
                if isinstance(prop, (tuple, list)):
                    prop_value = (tuple([p for p in prop
                                         if p not in prop_value]) +
                                  tuple(prop_value))

            obj._updateProperty(prop_id, prop_value)

    def _updateProperty(self, id, value):
        # Update the value of an existing property. If value
        # is a string, an attempt will be made to convert
        # the value to the type of the existing property.
        self._wrapperCheck(value)
        if not self.hasProperty(id):
            raise BadRequest, 'The property %s does not exist' % escape(id)
        if isinstance(value, basestring): # not only str
            proptype=self.getPropertyType(id) or 'string'
            if type_converters.has_key(proptype):
                value=type_converters[proptype](value)
        self._setPropValue(id, value)

# Do the patching

PropertyManagerHelpers._initProperties = _initProperties
PropertyManager._updateProperty = _updateProperty
