# (C) Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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
""" This is a patch for bug http://www.zope.org/Collectors/CMF/198/
  submitted by efge.

  Note that this patch requires PortalObjectBase.__getattr__ and __check_id
  patches.

  WARNING this patch is not compatible with Speedpack !
"""

from zLOG import LOG, INFO, DEBUG

from Products.CMFCore.Skinnable import SkinnableObjectManager, superGetAttr
from Acquisition import aq_base
from thread import get_ident

LOG('PatchCMFCoreSkinnableObjectManager', INFO,
    'CPSCore Patching CMFCore bug #198')

SKINDATA = {} # mapping thread-id -> (skinobj, ignore, resolve)
_marker = []  # Create a new marker object.

class SkinDataCleanup:
    """Cleanup at the end of the request."""
    def __init__(self, tid):
        self.tid = tid
    def __del__(self):
        tid = self.tid
        #LOG('SkinDataCleanup', DEBUG, 'Cleaning up skindata for %s' % tid)
        if SKINDATA.has_key(tid):
            del SKINDATA[tid]
        else:
            #LOG('SkinDataCleanup', DEBUG, 'MISSING %s' % tid)
            pass

def cmf___getattr__(self, name):
    '''
    Looks for the name in an object with wrappers that only reach
    up to the root skins folder.

    This should be fast, flexible, and predictable.
    '''
    if not name.startswith('_') and not name.startswith('aq_'):
        sd = SKINDATA.get(get_ident())
        if sd is not None:
            ob, ignore, resolve = sd
            if not ignore.has_key(name):
                if resolve.has_key(name):
                    return resolve[name]
                subob = getattr(ob, name, _marker)
                if subob is not _marker:
                    # Return it in context of self, forgetting
                    # its location and acting as if it were located
                    # in self.
                    retval = aq_base(subob)
                    resolve[name] = retval
                    return retval
                else:
                    ignore[name] = 1
    if superGetAttr is None:
        raise AttributeError, name
    return superGetAttr(self, name)
SkinnableObjectManager.__getattr__ = cmf___getattr__


def cmf_changeSkin(self, skinname):
    '''Change the current skin.

    Can be called manually, allowing the user to change
    skins in the middle of a request.
    '''
    skinobj = self.getSkin(skinname)
    if skinobj is not None:
        tid = get_ident()
        #LOG('changeSkin', DEBUG, 'Setting up skindata for %s' % tid)
        SKINDATA[tid] = (skinobj, {}, {})
        REQUEST = getattr(self, 'REQUEST', None)
        if REQUEST is not None:
            REQUEST._hold(SkinDataCleanup(tid))
SkinnableObjectManager.changeSkin = cmf_changeSkin


def cmf_setupCurrentSkin(self, REQUEST=None):
    '''
    Sets up skindata so that __getattr__ can find it.

    Can NOT be called manually to change skins in the middle of a
    request! Use changeSkin for that.
    '''
    if REQUEST is None:
        REQUEST = getattr(self, 'REQUEST', None)
    if REQUEST is None:
        # self is not fully wrapped at the moment.  Don't
        # change anything.
        return
    if SKINDATA.has_key(get_ident()):
        # Already set up for this request.
        return
    skinname = self.getSkinNameFromRequest(REQUEST)
    self.changeSkin(skinname)
SkinnableObjectManager.setupCurrentSkin = cmf_setupCurrentSkin


def cmf__checkId(self, id, allow_dup=0):
    '''
    Override of ObjectManager._checkId().

    Allows the user to create objects with IDs that match the ID of
    a skin object.
    '''
    superCheckId = SkinnableObjectManager.inheritedAttribute('_checkId')
    if not allow_dup:
        # Temporarily disable skindata.
        # Note that this depends heavily on Zope's current thread
        # behavior.
        tid = get_ident()
        sd = SKINDATA.get(tid)
        if sd is not None:
            del SKINDATA[tid]
        try:
            base = getattr(self,  'aq_base', self)
            if not hasattr(base, id):
                # Cause _checkId to not check for duplication.
                return superCheckId(self, id, allow_dup=1)
        finally:
            if sd is not None:
                SKINDATA[tid] = sd
    return superCheckId(self, id, allow_dup)
SkinnableObjectManager._checkId = cmf__checkId

LOG('PatchCMFCoreSkinnableObjectManager', DEBUG, 'Patched')
