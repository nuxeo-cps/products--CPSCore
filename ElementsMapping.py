# (c) 2002-2003 Nuxeo SARL <http://nuxeo.com/>
# (c) 2002-2003 Julien Jalon <mailto:jj@nuxeo.com>
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

from zLOG import LOG, DEBUG

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from EventServiceTool import getEventService

from Acquisition import aq_base, aq_parent, aq_chain

_marker = []

def call_meth(meth, elements):
    if getattr(aq_base(meth), 'isDocTemp', 0):
        return meth(aq_parent(meth), elements['REQUEST'])
    else:
        return meth()

class ElementPlaceHolder:
    """\
    An element place holde just deffers the call to
    elements[name] until it is really desired
    """

    security = ClassSecurityInfo()
    security.setDefaultAccess('allow')

    _isPlaceHolder = 1

    def __init__(self, elements, name):
        self._elements = elements
        self._name = name

    def __call__(self):
        return self._elements[self._name]

InitializeClass(ElementPlaceHolder)

def _normalizeObject(a):
    """\
    Call a if a is an element place holder or a call element
    """
    b = aq_base(a)
    if hasattr(b, '_isPlaceHolder') or hasattr(b, '_isCallElement'):
        return b()
    else:
        return a

class ElementsMapping:
    """\
    An ElementsMapping is almost like a classic mapping
    except it can defer some element computations and other
    nice things
    """

    security = ClassSecurityInfo()
    security.setDefaultAccess('allow')

    def __init__(self, request, defaults=None):
        """\
        - request is the ZPublisher request

        - defaults is an object which fills elements default content
          it is done lazily so this object shoud have two methods:

          - _getDefaultElementsKeys() which returns the keys this object
            can set

          - _setDefaultElement(elements, name) which effectively fills
            elements with element 'name' (it can also fills other
            elements)

        Elements mapping caches itself in request.other['elements_mapping']
        """
        self._request = request
        if defaults is not None:
            self._default_keys = list(defaults._getDefaultElementsKeys())
            self._default_setter = defaults._setDefaultElement
        else:
            self._default_keys = []
        self._mapping = {}
        self._sequences = {}
        self._appending = {}
        self['REQUEST'] = request
        request.other['elements_mapping'] = self

    def _getElement(self, name, default=_marker):
        """\
        Get element named 'name'. Try to set it if necessary
        from the default setter
        """
        mapping = self._mapping
        if mapping.has_key(name):
            return mapping[name]
        elif not self._appending.has_key(name) and\
                name in self._default_keys:
            self._appending[name] = None
            self._default_setter(self, name)
            return mapping[name]
        if default is not _marker:
            return default
        else:
            raise KeyError, name

    def __getitem__(self, name):
        """\
        Get element named 'name'. Expand sequences and calculate
        element place holders and call elements
        """
        if self._sequences.has_key(name):
            # expand sequence element
            result = []
            for extend, value in self._mapping[name]:
                value = _normalizeObject(value)
                if extend:
                    result.extend(value)
                else:
                    result.append(value)
            del self._sequences[name]
            self._mapping[name] = result
            return result
        else:
            result = _normalizeObject(self._getElement(name))
            # for now elements are cached in REQUEST
            self._mapping[name] = result
            return result

    def __setitem__(self, name, value):
        """Classic mapping method"""
        self._mapping[name] = value
        if self._appending.has_key(name):
            del self._appending[name]

    # for Zope Guards
    __guarded_setitem__ = __setitem__

    def get(self, name, default=None):
        """Classic mapping method"""
        if self._mapping.has_key(name):
            return self[name]
        else:
            return default

    def set(self, name, value):
        self[name] = value

    def has_key(self, name):
        """Classic mapping method"""
        return self._mapping.has_key(name) or name in self._default_keys

    def keys(self):
        """\
        Return all keys for this mapping including keys promised by
        the default setter
        """
        base_keys = self._mapping.keys()
        for key in self._default_keys:
            if key not in base_keys:
                base_keys.append(key)
        return base_keys

    def appendElement(self, name, value):
        """\
        Append an element to element named 'name'
        Turn element 'name' into a sequence element.
        If default setter does not set this element,
        [] is always the basis of this sequence element.
        """
        if self._sequences.has_key(name):
            self._mapping[name].append((0, value))
        else:
            self._sequences[name] = None
            a = self._getElement(name, [])
            self._mapping[name] = [(1, a), (0, value)]
            if self._appending.has_key(name):
                del self._appending[name]

    def extendElement(self, name, value):
        """\
        As appendElement() but extend element named 'name'
        """
        if self._sequences.has_key(name):
            self._mapping[name].append((1, value))
        else:
            self._sequences[name] = None
            a = self._getElement(name, [])
            self._mapping[name] = [(1, a), (1, value)]

    def getElementPlaceHolder(self, name):
        """\
        Return an object replacing self[name] until it is really
        necessary to evaluates it
        """
        return ElementPlaceHolder(self, name)

    # Call elements

    def setCallElement(self, name, object, method_name):
        self[name] = CallElement(self, object, method_name)

    def setActionCallElement(self, name, object, action_name):
        self[name] = ActionCallElement(self, object, action_name)

    def appendCallElement(self, name, object, method_name):
        self.appendElement(name, CallElement(self, object, method_name))

    def extendCallElement(self, name, object, method_name):
        self.extendElement(name, CallElement(self, object, method_name))

    def appendActionCallElement(self, name, object, method_name):
        self.appendElement(name, ActionCallElement(self, object, method_name))

    def extendActionCallElement(self, name, object, method_name):
        self.extendElement(name, ActionCallElement(self, object, method_name))

    def __repr__(self):
        return repr(dict(self))

InitializeClass(ElementsMapping)

class CallElement:

    _isCallElement = 1

    def __init__(self, elements, object, method_name):
        self._elements = elements
        self._object = object
        self._method_name = method_name

    def _callIt(self):
        object = _normalizeObject(self._object)
        meth = object.restrictedTraverse(self._method_name)
        if callable(meth):
            return call_meth(meth, self._elements)
        else:
            return meth

    def __call__(self):
        return self._callIt()

class ActionCallElement(CallElement):

    def _callIt(self):
        object = _normalizeObject(self._object)
        ti = object.getTypeInfo()
        action = ti.getActionById(self._method_name)
        if action:
            meth = object.restrictedTraverse(action)
        else:
            meth = object
        if callable(meth):
            result = call_meth(meth, self._elements)
            evtool = getEventService(object)
            evtool.notify(self._method_name, object, None)
            return result
        else:
            evtool.notify(self._method_name, object, None)
            return meth
