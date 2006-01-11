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

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
import logging
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.permissions import ManagePortal
from Products.GenericSetup.tool import SetupTool
from Products.GenericSetup.registry import _profile_registry
from Products.GenericSetup import BASE, EXTENSION

from Products.CPSCore.upgrade import listUpgradeSteps
from Products.CPSCore.interfaces import ICPSSite

DEFAULT_VERSION = '3.2.0' # If we've never upgraded, start there

LOG = logging.getLogger('CPSCore.setuptool')

class CPSSetupTool(UniqueObject, SetupTool):
    """CPS Setup Tool.

    Compared to the GenericSetup tool, it has some upgrade capabilities
    and simpler interface.
    """

    id = 'portal_setup'
    meta_type = 'CPS Setup Tool'

    security = ClassSecurityInfo()

    def __init__(self):
        SetupTool.__init__(self, self.id)

    def getEncoding(self):
        """See ISetupTool.
        """
        return 'iso-8859-15'

    security.declareProtected(ManagePortal, 'listProfileInfo')
    def listProfileInfo(self):
        """Get CPS profiles.

        Returns a list of info mappings. Base profile is listed first,
        extensions are sorted.

        Used by ZMI tool properties form (called by listContextInfos).
        """
        base = []
        ext = []
        for info in _profile_registry.listProfileInfo(for_=ICPSSite):
            if info['for'] == None:
                # Only keep CPS-specific profiles
                continue
            if info.get('type', BASE) == BASE:
                base.append(info)
            else:
                ext.append(info)
        ext.sort(lambda x,y: cmp(x['id'], y['id']))
        return base + ext

    #
    # Upgrades management
    #

    def _getCurrentVersion(self):
        portal = getToolByName(self, 'portal_url').getPortalObject()
        current = getattr(aq_base(portal), 'last_upgraded_version', '')
        current = current or DEFAULT_VERSION
        return tuple(current.split('.'))

    def _setCurrentVersion(self, version):
        portal = getToolByName(self, 'portal_url').getPortalObject()
        version = '.'.join(version)
        portal.last_upgraded_version = version
        return version

    security.declareProtected(ManagePortal, 'listUpgrades')
    def listUpgrades(self):
        """Get the list of available upgrades.
        """
        portal = getToolByName(self, 'portal_url').getPortalObject()
        source = self._getCurrentVersion()
        upgrades = listUpgradeSteps(portal, source)
        res = []
        for info in upgrades:
            info = info.copy()
            info['haspath'] = info['source'] and info['dest']
            info['ssource'] = '.'.join(info['source'] or ('all',))
            info['sdest'] = '.'.join(info['dest'] or ('all',))
            res.append(info)
        return res

    security.declarePrivate('doUpgrades')
    def doUpgrades(self, upgrades):
        portal = getToolByName(self, 'portal_url').getPortalObject()
        dests = {} # possible dest versions
        skipped = {} # some skipped upgrades for dest version
        for info in self.listUpgrades():
            dest = info['dest']
            dests[dest] = True
            if info['id'] not in upgrades:
                if info['proposed']:
                    skipped[dest] = True
                continue

            LOG.info("Running upgrade step %s (%s to %s)",
                     info['title'], info['ssource'], info['sdest'])
            info['step'].doStep(portal)

        # Update last_upgraded_version
        if None in dests:
            del dests[None]
        dests = dests.keys()
        dests.sort()
        # Keep highest non-skipped dest
        next = None
        for dest in dests:
            if dest in skipped:
                break
            next = dest
        if next is not None and next > self._getCurrentVersion():
            version = self._setCurrentVersion(next)
            LOG.info("Upgrading portal to %s", version)

    #
    # ZMI
    #

    manage_options = (({'label' : 'Upgrades',
                        'action' : 'manage_upgrades'
                       },) +
                      SetupTool.manage_options[1:5] + # props, I/O, snapshot
                      SetupTool.manage_options[:1] + # content
                      SetupTool.manage_options[5:]) # comparison, etc...

    security.declareProtected(ManagePortal, 'manage_upgrades')
    manage_upgrades = PageTemplateFile('zmi/setup_upgrades', globals())

    def manage_doUpgrades(self, REQUEST, upgrades=()):
        """Do upgrades.
        """
        self.doUpgrades(upgrades)
        REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_upgrades')

InitializeClass(CPSSetupTool)
