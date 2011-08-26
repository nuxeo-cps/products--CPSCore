import logging
import transaction
from App.version_txt import getZopeVersion
from Products.PluginIndexes.common.UnIndex import UnIndex
from Products.CPSCore.utils import IMAGE_RESIZING_CACHE


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

def check_disable_local_site_hook(portal):
    """Simple version check on Zope.

    This is necessary because the notion of upgraded version is quite different
    from actual code version.
    """
    return getZopeVersion() >= (2, 10)

def upgrade_image_caches(portal):
    logger = logging.getLogger(
        'Products.CPSDocument.upgrades.image_gallery_unidim_thumbnails')
    logger.info("Starting.")

    repotool = portal.portal_repository
    done = 0
    todo = len(repotool)

    def commit_log():
        logger.info(
            "Upgraded %d documents over %d", done, todo)
        transaction.commit()

    for c, doc in enumerate(repotool.iterValues()):
        if doc.hasObject(IMAGE_RESIZING_CACHE):
            cache = getattr(doc, IMAGE_RESIZING_CACHE)
            if cache.meta_type == 'Folder':
                doc._delObject(IMAGE_RESIZING_CACHE, suppress_events=True)
                done += 1

        if c and not (c % 100):
            commit_log()

    commit_log()
