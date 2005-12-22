# (C) Copyright 2002, 2003 Nuxeo SARL <http://nuxeo.com>
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
"""Proxy Tool that manages proxy objects and their links to real documents.
"""

from zLOG import LOG, ERROR, DEBUG, TRACE
from Globals import InitializeClass, DTMLFile
from types import DictType
from Acquisition import aq_base, aq_parent, aq_inner
from AccessControl import Unauthorized
from AccessControl import ClassSecurityInfo
from AccessControl.PermissionRole import rolesForPermissionOn
from BTrees.OOBTree import OOBTree

from Products.CMFCore.permissions import View
from Products.CMFCore.permissions import ManagePortal
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.utils import SimpleItemWithProperties
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import mergedLocalRoles
from Products.CMFCore.TypesTool import FactoryTypeInformation
from Products.CMFCore.TypesTool import ScriptableTypeInformation

from Products.CPSCore.EventServiceTool import getEventService
from Products.CPSCore.permissions import ViewArchivedRevisions
from Products.CPSCore.ProxyBase import ProxyBase, SESSION_LANGUAGE_KEY, \
     REQUEST_LANGUAGE_KEY
from Products.CPSUtil.session import sessionGet

from zope.app.event.interfaces import IObjectModifiedEvent
from zope.app.container.interfaces import IObjectMovedEvent
from OFS.interfaces import IObjectWillBeMovedEvent
from Products.CPSCore.interfaces import ICPSProxy


def handleObjectEvent(ob, event):
    """Notification from the event service.

    This looks up the local utility ProxyTool and calls it.
    Will be done with a real local utility later.
    """
    pxtool = getToolByName(ob, 'portal_proxies', None)
    if pxtool is None:
        return
    pxtool.handleObjectEvent(ob, event)


class ProxyTool(UniqueObject, SimpleItemWithProperties):
    """The proxy tool caches global informations about all proxies.

    The global information is used to find quickly all the proxies
    matching certain criteria:

    - rpath -> (docid, {lang: rev})

    - docid -> [rpaths]

    - docid, rev -> [rpaths]



    - also workflow state ?

    The proxy tool must be registered with the event service to receive
    sys_add_object and sys_del_object events, with action 'proxy'.
    """

    id = 'portal_proxies'
    meta_type = 'CPS Proxies Tool'
    use_portal_default_lang = False
    ignore_events = False

    _properties = SimpleItemWithProperties._properties + (
        {'id': 'use_portal_default_lang', 'type': 'boolean', 'mode': 'w',
         'label': "Use translation_service default prior to proxies default "
                  "when current lang not found"},
        {'id': 'ignore_events', 'type': 'boolean', 'mode': 'w',
         'label': "Ignore events (DO NOT USE)"},
        )

    security = ClassSecurityInfo()

    def __init__(self):
        self._clear()

    def _clear(self):
        self._rpath_to_infos = OOBTree()
        self._docid_rev_to_rpaths = OOBTree()
        self._docid_to_rpaths = OOBTree()

    #
    # External API
    #

    security.declarePrivate('createEmptyProxy')
    def createEmptyProxy(self, proxy_type, container, type_name, id,
                         docid=None):
        """Create an empty proxy.

        If docid is None, generate a new one.

        (Called by WorkflowTool.)
        """
        #LOG('ProxyTool', TRACE, "createEmptyProxy called with proxy_type=%s "
        #    "container=%s type_name=%s id=%s docid=%s"
        #    % (proxy_type, container.getId(), type_name, id, docid))
        proxy_type_name = {
            'folder':            'CPS Proxy Folder',
            'folderishdocument': 'CPS Proxy Folderish Document',
            'btreefolder':            'CPS Proxy BTree Folder',
            'btreefolderishdocument': 'CPS Proxy BTree Folderish Document',
            }.get(proxy_type,    'CPS Proxy Document')
        if docid is None:
            repotool = getToolByName(self, 'portal_repository')
            docid = repotool.getFreeDocid()
        proxy = self.constructContent(container,
                                      proxy_type_name, id,
                                      final_type_name=type_name,
                                      docid=docid)
        return proxy


    security.declarePrivate('createRevision')
    def createRevision(self, proxy_, lang_, from_lang_=None, *args, **kw):
        """Create a language's revision for a proxy.

        Returns the revision. Set from_lang_ (e.g. 'en' or 'fr', etc.) if you
        want to copy content from another language revision.

        (Called by WorkflowTool.)
        """
        proxy = proxy_ # prevent name collision in **kw
        lang = lang_
        from_lang = from_lang_
        language_revs = proxy._getLanguageRevisions()
        #LOG('ProxyTool', TRACE, "createRevision lang=%s for %s from lang=%s" %
        #    ('/'.join(proxy.getPhysicalPath()), lang, from_lang))
        if language_revs.has_key(lang):
            raise ValueError('Language revision %s already exists' % lang)
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()
        type_name = proxy.getPortalTypeName()
        if from_lang is not None:
            if language_revs.has_key(from_lang):
                from_rev = language_revs[from_lang]
            else:
                from_rev = language_revs[proxy.getDefaultLanguage()]
            ob, rev = repotool.copyRevision(docid, from_rev)
        else:
            ob, rev = repotool.createRevision(docid, type_name, *args, **kw)
        if hasattr(aq_base(ob), 'setLanguage'):
            ob.setLanguage(lang)
        proxy.setLanguageRevision(lang, rev)
        # Notify proxy of change (and so reindex)
        proxy.proxyChanged()
        #LOG('ProxyTool', TRACE, "  created rev=%s" % rev)
        return rev


    security.declarePrivate('checkoutRevisions')
    def checkoutRevisions(self, proxy, new_proxy, language_map):
        """Checkout a proxy's revisions into a new proxy.

        Uses a language map to decide the language correspondances.

        All copied revisions are frozen.
        """
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()

        if language_map is None:
            # Keep same languages, simple checkout.
            for lang, rev in proxy._getLanguageRevisions().items():
                repotool.freezeRevision(docid, rev)
                new_proxy.setLanguageRevision(lang, rev)

        else:
            # Checkout with specific languages.
            for new_lang, lang in language_map.items():
                real_lang, rev = self.getBestRevision(proxy, lang)
                if new_lang == real_lang:
                    new_rev = rev
                    repotool.freezeRevision(docid, rev)
                else:
                    # Create a new revision, because the language changed.
                    new_ob, new_rev = repotool.copyRevision(docid, rev)
                    if hasattr(aq_base(new_ob), 'setLanguage'):
                        new_ob.setLanguage(new_lang)
                        # XXX reindex ?

                new_proxy.setLanguageRevision(new_lang, new_rev)

        new_proxy.proxyChanged()


    security.declarePrivate('checkinRevisions')
    def checkinRevisions(self, proxy, dest_proxy):
        """Checkin a proxy's revisions into a destination proxy.

        Also used for proxy merge.
        """
        if proxy.getDocid() != dest_proxy.getDocid():
            raise ValueError('Proxies have different docids.')
        for lang, rev in proxy._getLanguageRevisions().items():
            dest_proxy.setLanguageRevision(lang, rev)
        dest_proxy.proxyChanged()

    security.declarePrivate('listProxies')
    def listProxies(self, docid=None):
        """List all proxies.

        If docid is not None, keep only those docids.

        Returns a sequence of (rpath, (docid, language_revs)).
        NOTE that the language_revs mapping should not be mutated!
        """
        if docid is None:
            all = list(self._rpath_to_infos.items())
        else:
            rpaths = self._docid_to_rpaths.get(docid, ())
            all = []
            for rpath in rpaths:
                infos = self._rpath_to_infos[rpath]
                all.append((rpath, infos))
        all.sort() # Sort by rpath.
        return all

    security.declarePrivate('getBestRevision')
    def getBestRevision(self, proxy, lang=None):
        """Get the best language and revision for a proxy.

        Returns lang, rev. A priority is made for the language :
          - Use the 'lang' parameter (can be 'default')
          - Use a REQUEST or SESSION override set on that proxy
          - Use the translation_service selected language
          - Use the portal default language
          - Use the proxy default language
          - Use the first language found in tricky situations (fallback).
        """
        language_revs = proxy._getLanguageRevisions()
        languages = language_revs.keys()
        languages_count = len(languages)

        if languages_count == 0:
            # Proxy construction not finished.
            return None, None
        # XXX fix absolute_url is not unit test friendly
        #LOG('ProxyTool.getBestRevision', TRACE,
        #    'proxy:%s lang:%s languages: %s' % (proxy.absolute_url(),
        #                                        lang, languages))
        if lang == 'default':
            lang = proxy.getDefaultLanguage()
        last_check = 'NOCHOICE'
        for check in ('ANYCHOICE?',
                      'REQUEST', 'TRANSLATION_SERVICE', 'PROXY', 'DEFAULT'):
            if lang in languages:
                break # found a language, exit loop

            if check == 'ANYCHOICE?':
                if languages_count == 1:
                    lang = languages[0]  # 0/ no choice
            elif check == 'REQUEST':
                REQUEST = getattr(proxy, 'REQUEST', None)
                if REQUEST is not None:
                    # 1.1/ check REQUEST
                    if isinstance(REQUEST, DictType):
                        switcher = REQUEST.get(REQUEST_LANGUAGE_KEY)
                    else:
                        switcher = getattr(REQUEST, REQUEST_LANGUAGE_KEY, None)
                    # 1.2/ check SESSION
                    if switcher is None:
                        check += ' SESSION'
                        switcher = sessionGet(REQUEST, SESSION_LANGUAGE_KEY,
                                              None)
                    if switcher is not None:
                        utool = getToolByName(self, 'portal_url')
                        rpath = utool.getRelativeUrl(proxy)
                        lang = switcher.get(rpath)
            elif check == 'TRANSLATION_SERVICE':
                translation_service = getToolByName(
                    self, 'translation_service', None)
                if translation_service is not None:
                    # 2.1/ try user-preferred language
                    lang = translation_service.getSelectedLanguage()
                    if lang not in languages:
                        # 2.2/ try portal-preferred language
                        if self.isUsePortalDefaultLang():
                            lang = translation_service.getDefaultLanguage()
            elif check == 'PROXY':
                # 3/ try default proxy lang
                lang = proxy.getDefaultLanguage()
            else:
                # 4/ fallback take the first available
                # this should not happen using the API
                languages.sort()
                lang = languages[0]
            last_check = check

        #LOG('ProxyTool.getBestRevision', TRACE,
        #    'return lang: %s, rev: %s choice: %s' %
        #    (lang, language_revs[lang], last_check))
        return lang, language_revs[lang]


    security.declarePrivate('getContent')
    def getContent(self, proxy, lang=None, rev=None, editable=0):
        """Get the object best matched by a given proxy.

        Returns the object.
        Raises KeyError if the language cannot be found.

        If lang is not passed, takes into account the user language.

        If rev is passed, this specific revision is returned.

        If editable, the returned content must be an unfrozen version,
        so a cloning and a version upgrade may happen behind the scene.

        (Called by ProxyBase.)
        """
        repotool = getToolByName(self, 'portal_repository')

        docid = proxy.getDocid()
        rev_wanted = rev

        # Find version to use.
        lang, rev = self.getBestRevision(proxy, lang=lang)
        if lang is None:
            return None # Proxy not yet finished.

        if rev_wanted is not None:
            if repotool.hasObjectRevision(docid, rev_wanted):
                rev = rev_wanted

        if editable:
            newob, newrev = repotool.getUnfrozenRevision(docid, rev)

            #LOG('ProxyTool', TRACE,
            #    'getContent editable, rev=%s -> %s' % (rev, newrev))

            if newrev != rev:
                proxy.setLanguageRevision(lang, newrev)
                proxy.proxyChanged()

            return newob

        return repotool.getObjectRevision(docid, rev)

    security.declarePrivate('getContentByRevision')
    def getContentByRevision(self, docid, rev):
        """Return an object for docid and rev.

        Returns None if the there is no such object.
        """
        repotool = getToolByName(self, 'portal_repository')
        if repotool.hasObjectRevision(docid, rev):
            return repotool.getObjectRevision(docid, rev)
        else:
            return None

    # XXX was def getProxyInfoFromRepoId(self, repoid, workflow_vars=()):
    security.declarePublic('getProxyInfosFromDocid')
    def getProxyInfosFromDocid(self, docid, workflow_vars=()):
        """Get the proxy infos from a docid.

        Returns a list of info, or raises KeyError if there is no proxy
        corresponding to docid.

        Info is a dict with:

        - object: the proxy

        - rpath: the proxy path relative to the portal

        - visible: a boolean describing the visibility of the proxy

        - language_revs: the revisions for each language

        - all specified workflow vars.

        (Called by user code to get object full history.)
        """
        wftool = getToolByName(self, 'portal_workflow')
        portal = aq_parent(aq_inner(self))
        rpaths = self._docid_to_rpaths[docid]
        res = []
        for rpath in rpaths:
            try:
                ob = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', DEBUG,
                    'getProxiesFromRepoId no ob rpath=%s' % rpath)
                continue
            docid2, language_revs = self._rpath_to_infos[rpath]
            visible = _checkPermission(View, ob)
            info = {'object': ob,
                    'rpath': rpath,
                    'language_revs': language_revs,
                    'visible': visible,
                    }
            for var in workflow_vars:
                info[var] = wftool.getInfoFor(ob, var, None)
            res.append(info)
        return res

    # XXX was def getProxiesFromId(self, id):
    security.declarePublic('getProxiesFromObjectId')
    def getProxiesFromObjectId(self, id, proxy_rpath_prefix=None):
        """Get the proxy infos from an object id (gotten from the catalog).

        Returns a list of dictionnaries with:

        - object: the proxy

        - rpath: the proxy's rpath

        - docid: the proxy docid

        - language_revs: the association between language and revs

        Only returns the proxies that are visible.

        (Called by user code after a catalog search.)
        XXX should be transformed into a full searchResults method XXX
        """
        repotool = getToolByName(self, 'portal_repository')
        portal = aq_parent(aq_inner(self))
        docid, rev = repotool.getDocidAndRevisionFromObjectId(id)
        if docid is None:
            return []
        rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
        res = []
        for rpath in rpaths:
            if proxy_rpath_prefix and not rpath.startswith(proxy_rpath_prefix):
                continue
            docid2, language_revs = self._rpath_to_infos[rpath]
            try:
                # XXX costly if search
                # XXX We should be able to filter by visibility directly
                ob = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', DEBUG,
                    'getProxiesFromObjectId rpath=%s id=%s' % (rpath, id))
                continue
            if _checkPermission(View, ob):
                info = {'object': ob,
                        'rpath': rpath,
                        'docid': docid,
                        'language_revs': language_revs.copy(),
                        }
                res.append(info)
        return res

    security.declarePrivate('getArchivedInfosForDocid')
    def getArchivedInfosForDocid(self, docid):
        """Get info about the archived revisions for a docid.

        Returns a list of dicts with info:
          rev, lang, modified, rpaths, is_frozen, is_archived

        (Called by ProxyBase.)
        """
        if not docid:
            return []
        repotool = getToolByName(self, 'portal_repository')
        revs = repotool.listRevisions(docid)
        res = []
        for rev in revs:
            ob = repotool.getObjectRevision(docid, rev)
            base_ob = aq_base(ob)
            #title = ob.title_or_id()
            rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
            if hasattr(base_ob, 'Language'):
                lang = ob.Language()
            elif hasattr(base_ob, 'language'):
                lang = ob.language
            else:
                lang = None
            if hasattr(base_ob, 'modified') and callable(ob.modified):
                modified = ob.modified()
            elif hasattr(base_ob, 'modification_date'):
                modified = ob.modification_date
            else:
                modified = None
            is_frozen = repotool.isRevisionFrozen(docid, rev)
            info = {
                'rev': rev,
                #'title': title, # security-sensitive
                'lang': lang or 'en',
                'modified': modified,
                'rpaths': rpaths,
                'is_frozen': is_frozen,
                'is_archived': not rpaths,
                }
            res.append(info)
        return res

    security.declarePrivate('delProxyArchivedRevisions')
    def delProxyArchivedRevisions(self, proxy, revs):
        """Delete some archived revisions of a proxy.
        """
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()

        # Check that revs are really archived.
        for rev in revs:
            if not repotool.hasObjectRevision(docid, rev):
                raise ValueError("Revision %s does not exist" % rev)
            rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
            if rpaths:
                raise ValueError("Revision %s is not archived" % rev)
        # Delete
        for rev in revs:
            repotool.delObjectRevision(docid, rev)

    security.declarePrivate('revertProxyToRevisions')
    def revertProxyToRevisions(self, proxy, language_revs, freeze):
        """Revert a proxy to older revisions.

        If freeze=1 (default), freeze the current revisions.
        """
        repotool = getToolByName(self, 'portal_repository')
        if freeze:
            proxy.freezeProxy()
        docid = proxy.getDocid()
        if not language_revs.has_key(proxy.getDefaultLanguage()):
            raise ValueError("Default language would be missing")
        for lang, rev in language_revs.items():
            if not repotool.hasObjectRevision(docid, rev):
                raise ValueError("No revision %s for docid %s" % (rev, docid))
            proxy.setLanguageRevision(lang, rev)
        proxy.proxyChanged()

    security.declarePrivate('_reindexProxiesForObject')
    def _reindexProxiesForObject(self, ob):
        """Reindex the proxies corresponding to a repository object.

        Also sends notification events (for these proxies).
        """
        evtool = getEventService(self)
        repotool = getToolByName(self, 'portal_repository')
        portal = aq_parent(aq_inner(self))
        docid, rev = repotool.getDocidAndRevisionFromObjectId(ob.getId())
        #LOG('ProxyTool', TRACE, '_reindexProxiesForObject docid=%s rev=%s'
        #    % (docid, rev))
        if docid is None:
            return
        rpaths = self._docid_rev_to_rpaths.get((docid, rev), ())
        for rpath in rpaths:
            docid2, language_revs = self._rpath_to_infos[rpath]
            try:
                # XXX costly if search
                # XXX We should be able to filter by visibility directly
                proxy = portal.unrestrictedTraverse(rpath)
            except KeyError:
                LOG('ProxyTool', ERROR,
                    '_reindexProxiesForObject no rpath=%s id=%s' % (rpath, id))
                continue
            #LOG('ProxyTool', TRACE, '_reindexProxiesForObject reindexing '
            #    'rpath=%s' % rpath)
            proxy.reindexObject()
            evtool.notify('sys_modify_object', proxy, {})

    # XXX implement this
    security.declarePublic('searchResults')
    def searchResults(self, **kw):
        """Return the proxies matching a search in the catalog.
        """
        raise NotImplementedError


    security.declarePrivate('freezeProxy')
    def freezeProxy(self, proxy):
        """Freeze a proxy.

        (Also called by ProxyBase.)
        """
        # XXX use an event?
        repotool = getToolByName(self, 'portal_repository')
        docid = proxy.getDocid()
        for lang, rev in proxy._getLanguageRevisions().items():
            #LOG('ProxyTool', DEBUG, ' Freezeing repoid=%s v=%s'
            #    % (repoid, version_info))
            repotool.freezeRevision(docid, rev)

    def _unshareContent(self, proxy, repotool):
        """Unshare content of a proxy.

        Puts new revisions into a new docid.
        """
        docid = proxy.getDocid()
        new_docid = repotool.getFreeDocid()
        for lang, rev in proxy._getLanguageRevisions().items():
            new_ob, new_rev = repotool.copyRevision(docid, rev, new_docid)
            proxy.setLanguageRevision(lang, new_rev)
        proxy.setDocid(new_docid)
        proxy.setFromLanguageRevisions({})
        proxy.setTag(None)
        history = repotool.getHistory(docid) or ()
        repotool.setHistory(new_docid, history)
        proxy.proxyChanged()

    def _unshareContentDoRecursion(self, proxy, repotool):
        """Unshare content, and recurse."""
        if not isinstance(proxy, ProxyBase):
            return
        self._unshareContent(proxy, repotool)
        for subob in proxy.objectValues():
            self._unshareContentDoRecursion(subob, repotool)

    security.declarePrivate('unshareContentRecursive')
    def unshareContentRecursive(self, proxy):
        """Unshare content

        Called after a copy+paste for instance. This is recursive.
        """
        repotool = getToolByName(self, 'portal_repository')
        self._unshareContentDoRecursion(proxy, repotool)

    #
    # XXX
    # This does object construction like TypesTool but without security
    # checks (which are already done by WorkflowTool).
    #

    def _constructInstance_fti(self, container, ti, id, *args, **kw):
        if not ti.product or not ti.factory:
            raise ValueError('Product factory for %s was undefined: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        p = container.manage_addProduct[ti.product]
        meth = getattr(p, ti.factory, None)
        if meth is None:
            raise ValueError('Product factory for %s was invalid: %s.%s'
                             % (ti.getId(), ti.product, ti.factory))
        if getattr(aq_base(meth), 'isDocTemp', 0):
            newid = meth(meth.aq_parent, self.REQUEST, id=id, *args, **kw)
        else:
            newid = meth(id, *args, **kw)
        newid = newid or id
        return container._getOb(newid)

    def _constructInstance_sti(self, container, ti, id, *args, **kw):
        constr = container.restrictedTraverse(ti.constructor_path)
        constr = aq_base(constr).__of__(container)
        return constr(container, id, *args, **kw)

    security.declarePrivate('constructContent')
    def constructContent(self, container, type_name, id, final_type_name=None,
                         *args, **kw):
        """Construct an CMFish object without all the security checks.

        Do not insert into any workflow.

        Returns the object.
        """
        ttool = getToolByName(self, 'portal_types')
        ti = ttool.getTypeInfo(type_name)
        if ti is None:
            raise ValueError('No type information for %s' % type_name)
        if isinstance(ti, FactoryTypeInformation):
            ob = self._constructInstance_fti(container, ti, id, *args, **kw)
        elif isinstance(ti, ScriptableTypeInformation):
            ob = self._constructInstance_sti(container, ti, id, *args, **kw)
        else:
            raise ValueError('Unknown type information class for %s' %
                             type_name)
        if ob.getId() != id:
            # Sanity check
            raise ValueError('Constructing %s, id changed from %s to %s' %
                             (type_name, id, ob.getId()))
        if final_type_name is None:
            final_type_name = type_name
        ob._setPortalTypeName(final_type_name)
        # Send a creation event with the correct portal_type set
        evtool = getEventService(self)
        evtool.notify('sys_add_object', ob, {})
        # Object has been constructed without indexing, index it now.
        ob.reindexObject()
        return ob

    #
    # Internal
    #

    security.declarePrivate('_addProxy')
    def _addProxy(self, proxy, rpath):
        """Add knowledge about a new proxy.

        Maintains internal indexes.

        We have to be flexible about receiving several adds for the same
        rpath. Because when a proxy is initially created it is without a
        portal_type, and after the portal_type is really set we have to
        send another sys_add_object so that subscribers caring about the
        portal_type see it created.
        """
        docid = proxy.getDocid()
        language_revs = proxy.getLanguageRevisions()

        rpaths = self._docid_to_rpaths.get(docid, ())
        if rpath not in rpaths:
            rpaths = rpaths + (rpath,)
            self._docid_to_rpaths[docid] = rpaths

        self._rpath_to_infos[rpath] = (docid, language_revs)

        revs = {}
        for lang, rev in language_revs.items():
            revs[rev] = None
        for rev in revs.keys():
            key = (docid, rev)
            rpaths = self._docid_rev_to_rpaths.get(key, ())
            if rpath not in rpaths:
                rpaths = rpaths + (rpath,)
                self._docid_rev_to_rpaths[key] = rpaths


    security.declarePrivate('_delProxy')
    def _delProxy(self, rpath):
        """Delete knowledge about a proxy.

        Maintains internal indexes.
        """
        docid, language_revs = self._rpath_to_infos[rpath]
        del self._rpath_to_infos[rpath]

        rpaths = list(self._docid_to_rpaths[docid])
        rpaths.remove(rpath)
        if rpaths:
            self._docid_to_rpaths[docid] = tuple(rpaths)
        else:
            del self._docid_to_rpaths[docid]

        revs = {}
        for lang, rev in language_revs.items():
            revs[rev] = None
        for rev in revs.keys():
            key = (docid, rev)
            rpaths = list(self._docid_rev_to_rpaths[key])
            rpaths.remove(rpath)
            if rpaths:
                self._docid_rev_to_rpaths[key] = tuple(rpaths)
            else:
                del self._docid_rev_to_rpaths[key]

    security.declarePrivate('_modifyProxy')
    def _modifyProxy(self, proxy, rpath):
        """Recompute knowledge about a proxy."""
        self._delProxy(rpath)
        self._addProxy(proxy, rpath)

    #
    # Event notification
    #

    # BBB will be removed in CPS 3.5
    security.declarePrivate('notify_proxy')
    def notify_proxy(self, event_type, ob, infos):
        """Old event service tool subscriber method, now unused.
        """
        return

    security.declarePrivate('handleObjectEvent')
    def handleObjectEvent(self, ob, event):
        """Notification from the event service.

        Called when a proxy is added/deleted/modified.

        Updates internal indexes.

        When a repository document is modified, reindexes the proxies
        and notifies of their modification.
        """
        if self.ignore_events:
            return

        # Proxy events
        if ICPSProxy.providedBy(ob):
            pplen = len(self.getPhysicalPath()) - 1
            rpath = '/'.join(ob.getPhysicalPath()[pplen:])
            if IObjectWillBeMovedEvent.providedBy(event):
                if event.oldParent is not None:
                    self._delProxy(rpath)
            elif IObjectMovedEvent.providedBy(event):
                if event.newParent is not None:
                    self._addProxy(ob, rpath)
            elif IObjectModifiedEvent.providedBy(event):
                self._modifyProxy(ob, rpath)

        # Repository modification events
        elif IObjectModifiedEvent.providedBy(event):
            repotool = getToolByName(self, 'portal_repository', None)
            if repotool is None:
                return
            if repotool.isObjectInRepository(ob):
                self._reindexProxiesForObject(ob)

    #
    # Management
    #

    security.declareProtected(ManagePortal, 'isUsePortalDefaultLang')
    def isUsePortalDefaultLang(self):
        """Returns a boolean (0 to python < 2.3 or True) wether the property
           'use_portal_default_lang' is checked.
        """
        return not not self.use_portal_default_lang

    security.declareProtected(ManagePortal, 'getRevisionsUsed')
    def getRevisionsUsed(self):
        """Return management info about all the proxies.

        Return a dict of {docid: dict of {rev: None}}
        """
        res = {}
        for rpath, infos in self._rpath_to_infos.items():
            docid, language_revs = infos
            for lang, rev in language_revs.items():
                res.setdefault(docid, {})[rev] = None
        return res

    security.declareProtected(ManagePortal, 'getBrokenProxies')
    def getBrokenProxies(self):
        """Return the broken proxies.

        Broken proxies are those that point to a non-existing repository
        object.

        Return a list of (rpath, infos).
        """
        repotool = getToolByName(self, 'portal_repository')
        broken = []
        for rpath, infos in self._rpath_to_infos.items():
            docid, language_revs = infos
            for lang, rev in language_revs.items():
                if not repotool.hasObjectRevision(docid, rev):
                    broken.append((rpath, infos))
                    break
        return broken

    security.declareProtected(ManagePortal, 'getBrokenIndexes')
    def getBrokenIndexes(self):
        """Return the broken indexes.

        Return a list of (rpath, infos).
        """
        portal = aq_parent(aq_inner(self))
        broken = []
        for rpath, infos in self._rpath_to_infos.items():
            try:
                ob = portal.unrestrictedTraverse(rpath)
            except (AttributeError, KeyError):
                broken.append((rpath, infos))
        return broken

    def _recurse_rebuild(self, ob, utool):
        """Rebuild all proxies recursively."""
        if not isinstance(ob, ProxyBase):
            return
        rpath = utool.getRelativeUrl(ob)
        self._addProxy(ob, rpath)
        for subob in ob.objectValues():
            self._recurse_rebuild(subob, utool)

    security.declareProtected(ManagePortal, 'rebuildProxyIndexes')
    def rebuildProxyIndexes(self):
        """Rebuild all proxy indexes."""
        utool = getToolByName(self, 'portal_url')
        portal = aq_parent(aq_inner(self))
        self._clear()
        # Use as roots all the subobs (1st level) of the portal.
        for ob in portal.objectValues():
            self._recurse_rebuild(ob, utool)

    #
    # ZMI
    #

    manage_options = (
        {'label': 'Management',
         'action': 'manage_proxiesInfo',
        },
        {'label': 'Proxies',
         'action': 'manage_listProxies',
        },
        ) + SimpleItemWithProperties.manage_options

    security.declareProtected(ManagePortal, 'manage_proxiesInfo')
    manage_proxiesInfo = DTMLFile('zmi/proxy_proxiesInfo', globals())

    security.declareProtected(ManagePortal, 'manage_listProxies')
    manage_listProxies = DTMLFile('zmi/proxy_list_proxies', globals())

    security.declareProtected(ManagePortal, 'manage_purgeBrokenIndexes')
    def manage_purgeBrokenIndexes(self, REQUEST=None):
        """Purge the broken indexes."""
        broken = self.getBrokenIndexes()
        for rpath, infos in broken:
            self._delProxy(rpath)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/manage_proxiesInfo?searchbrokenindexes=1'
                                  '&manage_tabs_message=Purged.')

    security.declareProtected(ManagePortal, 'manage_purgeBrokenProxies')
    def manage_purgeBrokenProxies(self, REQUEST=None):
        """Purge the broken proxies."""
        portal = aq_parent(aq_inner(self))
        broken = self.getBrokenProxies()
        for rpath, infos in broken:
            LOG('purgeBrokenProxies', DEBUG, 'Purging %s' % rpath)
            ob = portal.unrestrictedTraverse(rpath)
            container = aq_parent(aq_inner(ob))
            container.manage_delObjects([ob.getId()])
            # Shouldn't be necessary but exception during del...
            self._delProxy(rpath)
        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/manage_proxiesInfo?searchbrokenindexes=1'
                                  '&manage_tabs_message=Purged.')

InitializeClass(ProxyTool)
