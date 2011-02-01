# Copyright 2005-2008 Nuxeo SAS <http://nuxeo.com>
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

import os
from logging import getLogger
from os.path import abspath
import pickle
from ZODB.POSException import ConflictError
import Products
from Products.GenericSetup.utils import _resolveDottedName

logger = getLogger(__name__)

_upgrade_registry = {} # id -> step
# id -> dict with keys: title, portal_attr, floor_version
_categories_registry = {}

VERSION_FILE = 'VERSION'

class UpgradeStep(object):
    """A step to upgrade a component.
    """
    def __init__(self, category, title, source, dest, handler,
                 checker=None, sortkey=0, requires=None, version=1):
        """
        >>> ups = UpgradeStep('cpsgroupware', 'title', '1.0.0', '1.2', None,
        ...                   requires='cpsplatform-3.4.1')
        >>> ups.category
        'cpsgroupware'
        >>> ups.source
        (1, 0, 0)
        >>> ups.dest
        (1, 2)
        >>> ups.requires
        ('cpsplatform', (3, 4, 1))
        """
        self.id = str(hash((pickle.dumps(handler), category, version,
                            source, dest, sortkey)))

        self.title = title
        if source == '*':
            source = None
        elif isinstance(source, basestring):
            source = tuple(int(x) for x in source.split('.'))
        self.source = source
        if dest == '*':
            dest = None
        elif isinstance(dest, basestring):
            dest = tuple(int(x) for x in dest.split('.'))
        self.dest = dest
        self.handler = handler
        self.checker = checker
        self.version = version
        self.sortkey = sortkey
        self.category = category
        if requires:
            spl_req = requires.rsplit('-')
            requires = (spl_req[0], tuple(int(x) for x in spl_req[1].split('.')))
        self.requires = requires

    def __str__(self):
        return ('<CPSUpgradeStep id=%r category=%r '
                'source=%s dest=%s title=%r') % (
        self.id, self.category, self.source, self.dest, self.title)

    def doStep(self, portal):
        self.handler(portal)

    def isProposed(self, portal, cat, source):
        """Check if a step can be applied.

        False means already applied or does not apply.
        True means can be applied.
        """
        checker = self.checker
        vm = self.versionMatch(portal, source)
        return vm and (checker is None or checker(portal))

    def versionMatch(self, portal, source):
        """Check if a step should be applied relatively to its version.

        Return True if the source of the step is greater than the portal version
        number.
        """
        return (source is None or
                self.source is None or
                source <= self.source)


def _registerUpgradeStep(step):
    _upgrade_registry[step.id] = step
    logger.debug("registered %s", step)

def upgradeStep(_context, title, handler, source='*', destination='*',
                category='cpsplatform', sortkey=0, checker=None,
                version=1, requires=None):

    step = UpgradeStep(category, title, source, destination, handler,
                       checker=checker, sortkey=sortkey, requires=requires,
                       version=version)
    _context.action(
        discriminator = ('upgradeStep',
                         category, source, destination, handler, sortkey),
        callable = _registerUpgradeStep,
        args = (step,),
        )

def disableUpgradeSteps(handler, min_version=None, max_version=None):
    """Disable upgrade steps with given handler.

    min_version and max_version can be used to restrict this disabling to a
    range of versions of the step itself.
    """
    updateStepsChecker(handler, lambda portal: False,
                       min_version=min_version, max_version=max_version)

def updateStepsChecker(handler, checker,
                       min_version=None, max_version=None):
    """Change the checker for steps with prescribed handler.

    min_version and max_version can be used to restrict this disabling to a
    range of versions of the step itself.
    """

    if (min_version, max_version) == (None, None):
        version_check = lambda v: True
    elif min_version is None:
        version_check = lambda v: v <= max_version
    elif max_version is None:
        version_check = lambda v: v >= min_version
    else:
        version_check = lambda v: v >= min_version and v <= max_version

    for step in listUpgradesByHandler(handler):
        if not version_check(step.version):
            continue
        step.checker = checker


def registerUpgradeCategory(cid, title='', floor_version='',
                            portal_attribute='', description='',
                            ref_product=''):

    if not title:
        title = cid
    if not floor_version:
        floor_version = '0.0.0'
    if not portal_attribute:
        raise ValueError('Missing portal_attribute keyword argument.')

    if cid in _categories_registry:
        raise ValueError(
            "There's already a category with id %s registered in %s" %
            (cid, _categories_registry[cid]['defined_in']))

    info = {'title': title,
            'floor_version': floor_version,
            'portal_attr': portal_attribute,
            'description': description,
    }

    if ref_product:
        info['ref_product'] = ref_product
        # very Zope2 centric
        ProductsPath = [ abspath(ppath)  for ppath in Products.__path__ ]
        flag = False
        for ppath in ProductsPath:
            version_path = os.path.join(ppath, ref_product, VERSION_FILE)
            logger.debug('Fetching current version number for %s from file %s' % (
                ref_product, version_path))
            abs_path = version_path
            if os.path.exists(abs_path):
                version_file = open(version_path, 'r')
                lines = [l.strip() for l in version_file.readlines()]
                version_file.close()
                pref = 'PKG_VERSION='
                for l in lines:
                    if l.startswith(pref):
                        info['code_version'] = l[len(pref):]
                flag = True
                break
        if not flag:
            raise OSError('File %s not found for %s Product' % (VERSION_FILE, info['title']) )


    _categories_registry[cid] = info
    logger.info('registered category %s with info %s', cid, info)

def listUpgradeSteps(portal, category, source, max_dest=None):
    """Lists upgrade steps from given category available from a given version.
    """
    res = []
    for id, step in _upgrade_registry.items():
        if step.category != category:
            continue
        try:
            proposed = step.isProposed(portal, category, source)
        except ConflictError:
            raise
        except:
            # if the checker can't even run, not a good idea to propose the
            # step
            proposed = False

        # TODO: (GR) Document this obscure condition. what's the use case ?
        if (not proposed
            and source is not None
            and (step.source is None or source > step.source)):
            continue

        if max_dest and step.dest > max_dest:
            continue

        info = {
            'id': id,
            'step': step,
            'title': step.title,
            'source': step.source,
            'dest': step.dest,
            'proposed': proposed,
            }
        if step.requires is not None:
            info['requires'] = step.requires

        res.append(((step.source or '', step.sortkey, proposed), info))

    res.sort()
    res = [i[1] for i in res]

    return res

def listUpgradesByHandler(handler):
    """Return all upgrade steps that have this handler.

    The handler is the callable or a dotted name.
    Note that the same handler can be used several times, e.g, after correction
    of a step in a later version
    """
    if isinstance(handler, str):
        handler = _resolveDottedName(handler)
    return [s for  s in _upgrade_registry.values() if s.handler == handler]


######################################################################

from Products.PluginIndexes.common.UnIndex import UnIndex

def upgrade_334_335_repository_security(context):
    """Upgrade the repository to remove security synthesis remnants.

    Removes all local roles on the contained objects.
    Marks all objects as being in the repository.
    """
    PARTIAL_COMMIT_EVERY = 100
    repo = context.portal_url.getPortalObject().portal_repository
    count = 0
    for ob in repo.objectValues():
        changed = False
        if getattr(ob, '__ac_local_roles__', None) is not None:
            ob.__ac_local_roles__ = None
            changed = True
        if getattr(ob, '__ac_local_group_roles__', None) is not None:
            ob.__ac_local_group_roles__ = None
            changed = True
        if not getattr(ob, '_isInCPSRepository', False):
            repo._markObjectInRepository(ob)
            changed = True
        if changed:
            count += 1
            if (count % PARTIAL_COMMIT_EVERY) == 0:
                get_transaction().commit(1)
    return "%s repository objects updated" % count


def upgrade_335_336_catalog_unicode(context):
    """Upgrade the catalog to clean it up of unicode.

    Fixes indexes, metadata and lexicons.
    Also fixes bad objects that still have unicode titles.
    """
    INDEX_NAMES = ('Title', 'SearchableText')
    METADATA_NAMES = ('Title',)
    LEXICON_NAMES = ('cps_defaut_lexicon',) # sic
    OB_ATTRIBUTES = ('title',)
    RPATHS = ('sections', 'workspaces', 'workspaces/members')

    catalog = context.portal_catalog
    cat = catalog._catalog
    nbindexes = 0
    nbmetadata = 0
    nblexicons = 0
    nbobjects = 0

    # Indexes
    for index_name in INDEX_NAMES:
        index = cat.indexes.get(index_name)
        if index is None:
            continue
        if not isinstance(index, UnIndex):
            continue
        _index = index._index
        _unindex = index._unindex
        # Check if there's some unicode somewhere
        bad = []
        for key, value in _index.items():
            if isinstance(key, unicode):
                bad.append((key, value))
                nbindexes += 1
        for key, value in bad:
            del _index[key]
        for key, value in bad:
            key = key.encode('ISO-8859-15')
            _index[key] = value
            _unindex[value] = key

    # Metadata
    ixs = [cat.schema.get(metadata_name)
           for metadata_name in METADATA_NAMES]
    ixs = [i for i in ixs if i is not None]
    # Check if there's some unicode in the metadata
    bad = []
    for key, value in cat.data.items():
        for i in ixs:
            if isinstance(value[i], unicode):
                bad.append(key)
                nbmetadata += 1
                break
    for key in bad:
        value = list(cat.data[key])
        for i in ixs:
            if isinstance(value[i], unicode):
                value[i] = value[i].encode('ISO-8859-15')
        cat.data[key] = tuple(value)

    # Lexicons
    for lexicon_name in LEXICON_NAMES:
        lexicon = getattr(catalog, lexicon_name, None)
        if lexicon is None:
            continue
        # Check if some words are unicode
        bad = []
        for word, wid in lexicon._wids.items():
            if isinstance(word, unicode):
                bad.append((word, wid))
                nblexicons += 1
        for word, wid in bad:
            del lexicon._wids[word]
        for word, wid in bad:
            word = word.encode('ISO-8859-15')
            lexicon._wids[word] = wid
            lexicon._words[wid] = word

    # Fixup object who have old unicode attributes
    for rpath in RPATHS:
        proxy = context.restrictedTraverse(rpath, default=None)
        if proxy is None:
            continue
        langs = proxy.getLanguageRevisions().keys()
        for lang in langs:
            doc = proxy.getContent(lang=lang)
            some = False
            for attr in OB_ATTRIBUTES:
                v = getattr(doc, attr, None)
                if isinstance(v, unicode):
                    setattr(doc, attr, v.encode('ISO-8859-15'))
                    some = True
            if some:
                nbobjects += 1

    return ("Cleaned up: %s index entries, %s metadata entries, "
            "%s lexicon entries, %s objects" % (
            nbindexes, nbmetadata, nblexicons, nbobjects))
