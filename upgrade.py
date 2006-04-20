# Copyright 2005 Nuxeo SARL <http://nuxeo.com>
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

_upgrade_registry = {} # id -> step

class UpgradeStep(object):
    """A step to upgrade a component.
    """
    def __init__(self, title, source, dest, handler,
                 checker=None, sortkey=0):
        self.id = str(abs(hash('%s%s%s%s' % (title, source, dest, sortkey))))
        self.title = title
        if source == '*':
            source = None
        elif isinstance(source, basestring):
            source = tuple(source.split('.'))
        self.source = source
        if dest == '*':
            dest = None
        elif isinstance(dest, basestring):
            dest = tuple(dest.split('.'))
        self.dest = dest
        self.handler = handler
        self.checker = checker
        self.sortkey = sortkey

    def versionMatch(self, portal, source):
        return (source is None or
                self.source is None or
                source <= self.source)

    def isProposed(self, portal, source):
        """Check if a step can be applied.

        False means already applied or does not apply.
        True means can be applied.
        """
        checker = self.checker
        if checker is None:
            return self.versionMatch(portal, source)
        else:
            return checker(portal)

    def doStep(self, portal):
        self.handler(portal)


def _registerUpgradeStep(step):
    _upgrade_registry[step.id] = step

def upgradeStep(_context, title, handler, source='*', destination='*',
                sortkey=0, checker=None):
    step = UpgradeStep(title, source, destination, handler, checker, sortkey)
    _context.action(
        discriminator = ('upgradeStep', source, destination, handler, sortkey),
        callable = _registerUpgradeStep,
        args = (step,),
        )

def listUpgradeSteps(portal, source):
    """Lists upgrade steps available from a given version.
    """
    res = []
    for id, step in _upgrade_registry.items():
        proposed = step.isProposed(portal, source)
        if (not proposed
            and source is not None
            and (step.source is None or source > step.source)):
            continue
        info = {
            'id': id,
            'step': step,
            'title': step.title,
            'source': step.source,
            'dest': step.dest,
            'proposed': proposed,
            }
        res.append(((step.source or '', step.sortkey, proposed), info))
    res.sort()
    res = [i[1] for i in res]
    return res


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
