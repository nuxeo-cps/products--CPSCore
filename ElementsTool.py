# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
# Author: Julien Jalon <jj@nuxeo.com>
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

import OFS
from Globals import InitializeClass, DTMLFile
from Acquisition import aq_parent, aq_inner, aq_base
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import UniqueObject, SimpleItemWithProperties
from Products.CMFCore.CMFCorePermissions import ViewManagementScreens

from ElementsMapping import ElementsMapping

class DefaultElement(SimpleItemWithProperties):
    """\
    DefaultElement instances stores default elements to add in
    elements mapping
    """

    meta_type = 'CPS Default Element'

    _properties = (
        {
            'id': 'from_element',
            'type': 'string',
            'mode': 'w',
            'label': 'From element'
        },
        {
            'id': 'method_name',
            'type': 'string',
            'mode': 'w',
            'label': 'Method name'
        },
        {
            'id': 'description',
            'type': 'text',
            'mode': 'w',
            'label': 'Description'
        },
        {
            'id': 'cmf_action',
            'type': 'boolean',
            'mode': 'w',
            'label': 'CMF action'
        },
    )

    from_element = ''
    method_name = ''
    description = ''
    cmf_action = 0

    def __init__(self, id, from_element, method_name, description, cmf_action):
        self.id = id
        self.from_element = from_element
        self.method_name = method_name
        self.description = description
        self.cmf_action = cmf_action

InitializeClass(DefaultElement)

class ElementsTool(UniqueObject, OFS.Folder.Folder):
    """Elements tool is used to initialize elements mapping and
    and eventually getting it.
    """

    id = 'portal_elements'

    meta_type = 'CPS Elements Tool'

    security = ClassSecurityInfo()

    manage_options = (
        {
            'label': 'Default elements',
            'action': 'manage_editDefaultElementsForm',
        },
    ) + OFS.Folder.Folder.manage_options[1:]

    _properties = (
        {'id': 'bases', 'type': 'tokens', 'mode': 'w', 'label': 'Bases'},
    )

    bases = ['NAVIGATION_BASE', 'SITE_BASE']

    def getElements(self, request=None, object=None):
        """Return elements mapping with some default elements
        """
        if request is None:
            request = self.REQUEST
        if request.other.has_key('elements_mapping'):
            return request.other['elements_mapping']
        elements = ElementsMapping(request, self)
        portal = aq_parent(aq_inner(self))
        if object is None:
            object = portal
        elements['CONTEXT'] = object
        folder = object
        bases = self.bases + ['isPrincipiaFolderish']
        found = {}
        for base in bases:
            found[base] = None
        while folder is not None:
            base_folder = aq_base(folder)
            for base in bases:
                if found[base] is None:
                    if getattr(base_folder, base, 0):
                        found[base] = folder

            folder = aq_parent(aq_inner(folder))

        for base in self.bases:
            o = found[base]
            if o is None:
                elements[base] = portal
            else:
                elements[base] = o

        container = found['isPrincipiaFolderish']
        if container is None:
            elements['CONTAINER'] = portal
        else:
            elements['CONTAINER'] = container

        elements['PORTAL'] = portal
        return elements

    # For ElementsMapping

    def _getDefaultElementsKeys(self):
        return self.objectIds()

    def _setDefaultElement(self, elements, name):
        def_el = getattr(self, name)
        object = elements.getElementPlaceHolder(def_el.from_element)
        if def_el.cmf_action:
            elements.setActionCallElement(name, object, def_el.method_name)
        else:
            elements.setCallElement(name, object, def_el.method_name)

    #
    # ZMI
    #
    security.declareProtected(ViewManagementScreens,
        'manage_editDefaultElementsForm')
    manage_editDefaultElementsForm = DTMLFile(
        'zmi/editDefaultElementsForm', globals())

    manage_main = manage_editDefaultElementsForm

    security.declareProtected(ViewManagementScreens,
        'manage_addDefaultElement')
    def manage_addDefaultElement(self, name, from_element, method_name,
                                  description='', cmf_action=0, REQUEST=None):
        """Add a default element to elements mapping

        Virtually:
            elements['name'] = elements['from_element'].method_name()
        If cmf_action is true, use method_name as action name.
        """
        name = name.upper()
        from_element = from_element.upper()
        element = DefaultElement(name, from_element, method_name, 
            description, cmf_action)
        self._setObject(name, element)
        if REQUEST is not None:
            REQUEST.RESPONSE.redirect(
                '%s/manage_editDefaultElementsForm' % (self.absolute_url(), )
            )

InitializeClass(ElementsTool)
