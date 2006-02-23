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

import time
import logging
from urllib import urlencode

from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from Acquisition import aq_base
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
    def listUpgrades(self, show_old=False):
        """Get the list of available upgrades.
        """
        portal = getToolByName(self, 'portal_url').getPortalObject()
        if show_old:
            source = None
        else:
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
    def doUpgrades(self, upgrades, show_old=False):
        portal = getToolByName(self, 'portal_url').getPortalObject()
        dests = {} # possible dest versions
        skipped = {} # some skipped upgrades for dest version
        for info in self.listUpgrades(show_old=show_old):
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
    # Improved I/O
    #

    security.declarePrivate('_mangleTimestampName')
    def _mangleTimestampName(self, prefix, ext=None):
        """Create a mangled ID using a timestamp.
        """
        timestamp = time.gmtime()
        items = (prefix,) + timestamp[:6]
        if ext is None:
            fmt = '%s-%4d%02d%02d-%02d%02d%02d'
        else:
            fmt = '%s-%4d%02d%02d-%02d%02d%02d.%s'
            items += (ext,)
        return fmt % items

    security.declarePrivate('_makeReport')
    def _makeReport(self, prefix, context_id, result):
        """Create a report from some import results.
        """
        if context_id.startswith('profile-'):
            id = context_id[len('profile-'):]
            id = id.replace(':', '-')
            if id.endswith('-default'):
                id = id[:-len('-default')]
        else:
            id = 'snapshot'
        name = self._mangleTimestampName(prefix+'-'+id, 'log')
        self._createReport(name, result['steps'], result['messages'])

    security.declareProtected(ManagePortal, 'listContextInfos')
    def listContextInfos(self, only_bases=False):
        """List registered profiles and snapshots.
        """
        p_infos = [{'id': 'profile-%s' % info['id'], 'title': info['title']}
                   for info in self.listProfileInfo()
                   if info.get('type', BASE) == BASE or not only_bases]
        s_infos = [{'id': 'snapshot-%s' % info['id'], 'title': info['title']}
                   for info in self.listSnapshotInfo()]
        return tuple(p_infos + s_infos)

    security.declareProtected(ManagePortal, 'listBaseContextInfos')
    def listBaseContextInfos(self):
        """List base profiles and snapshots.
        """
        return self.listContextInfos(only_bases=True)

    security.declarePrivate('reinstallProfile')
    def reinstallProfile(self, context_id, create_report=True):
        """Reinstall a profile, with purge.
        """
        # Wipe out old registries
        self.__init__()

        # Import, with purge
        self.setImportContext(context_id)
        result = self.runAllImportSteps(purge_old=True)
        steps_run = "Steps run: %s" % ', '.join(result['steps'])

        # Create a report
        if create_report:
            self._makeReport('reinstall', context_id, result)

    security.declarePrivate('importProfile')
    def importProfile(self, context_id, create_report=True):
        """Import a profile, without purge.
        """
        # Import, without purge
        old_context_id = self.getImportContextID()
        self.setImportContext(context_id)
        result = self.runAllImportSteps(purge_old=False)
        steps_run = "Steps run: %s" % ', '.join(result['steps'])

        # Create a report
        if create_report:
            self._makeReport('import', context_id, result)

        # Keep context as current if it's not a snapshot
        if not context_id.startswith('profile-'):
            self.setImportContext(old_context_id)

    #
    # ZMI
    #

    manage_options = (({'label' : 'Upgrades',
                        'action' : 'manage_upgrades'
                       },
                       {'label' : 'Profiles',
                        'action' : 'manage_tool'
                       }) +
                      SetupTool.manage_options[2:5] + # I/O, snapshot
                      SetupTool.manage_options[:1] + # content
                      SetupTool.manage_options[5:]) # comparison, etc...

    security.declareProtected(ManagePortal, 'manage_upgrades')
    manage_upgrades = PageTemplateFile('zmi/setup_upgrades', globals())

    security.declareProtected(ManagePortal, 'manage_tool')
    manage_tool = PageTemplateFile('zmi/sutProperties', globals())

    security.declareProtected(ManagePortal, 'manage_importSteps')
    manage_importSteps = PageTemplateFile('zmi/sutImportSteps', globals())

    security.declareProtected(ManagePortal, 'manage_reinstallProfile')
    def manage_reinstallProfile(self, context_id, REQUEST):
        """Reinstall a profile.
        """
        if not context_id:
            msg = "Please select a profile."
            REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_tool?'+
                                      urlencode({'manage_tabs_message': msg}))
            return

        self.reinstallProfile(context_id)

        # Result message
        for info in self.listContextInfos():
            if info['id'] == context_id:
                title = info['title']
                break
        else:
            title = '?'
        msg = "Profile '%s' reinstalled." % info['title']
        REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_tool?'+
                                  urlencode({'manage_tabs_message': msg}))

    security.declareProtected(ManagePortal, 'manage_importProfile')
    def manage_importProfile(self, context_id, REQUEST):
        """Import a profile in non-purge mode.
        """
        if not context_id:
            msg = "Please select a profile."
            REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_tool?'+
                                      urlencode({'manage_tabs_message': msg}))
            return

        self.importProfile(context_id)

        # Result message
        for info in self.listContextInfos():
            if info['id'] == context_id:
                title = info['title']
                break
        else:
            title = '?'
        msg = "Profile '%s' imported." % info['title']
        REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_tool?'+
                                  urlencode({'manage_tabs_message': msg}))


    security.declareProtected(ManagePortal, 'manage_importSelectedSteps')
    def manage_importAllSteps(self, create_report=True, context_id=None):
        """ Import all steps.
        """
        if context_id is not None:
            self.setImportContext(context_id)
        else:
            context_id = self.getImportContextID()

        result = self.runAllImportSteps(purge_old=False)
        steps_run = "Steps run: %s" % ', '.join(result['steps'])

        if create_report:
            self._makeReport('import', context_id, result)

        return self.manage_importSteps(manage_tabs_message=steps_run,
                                       messages=result['messages'],
                                       management_view='Import')

    security.declareProtected(ManagePortal, 'manage_importSelectedSteps')
    def manage_importSelectedSteps(self, ids, run_dependencies,
                                   create_report=True, context_id=None):
        """Import the steps selected by the user.
        """
        if context_id is not None:
            self.setImportContext(context_id)
        else:
            context_id = self.getImportContextID()

        messages = {}
        if not ids:
            summary = "No steps selected."
        else:
            steps_run = []
            for step_id in ids:
                result = self.runImportStep(step_id,
                                            run_dependencies=run_dependencies,
                                            purge_old=False)
                steps_run.extend(result['steps'])
                messages.update(result['messages'])

            summary = "Steps run: %s" % ', '.join(steps_run)

            if create_report:
                self._makeReport('import-selected', context_id, result)

        return self.manage_importSteps(manage_tabs_message=summary,
                                       messages=messages,
                                       management_view='Import')


    security.declareProtected(ManagePortal, 'manage_doUpgrades')
    def manage_doUpgrades(self, REQUEST, upgrades=(), show_old=False):
        """Do upgrades.
        """
        self.doUpgrades(upgrades, show_old=show_old)
        REQUEST.RESPONSE.redirect(REQUEST.URL1+'/manage_upgrades')

InitializeClass(CPSSetupTool)
