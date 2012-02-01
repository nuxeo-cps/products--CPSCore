import logging
from Products.GenericSetup import zcml as gs_zcml

logger = logging.getLogger(__name__)

def cleanUp():
    """Robuster version of Products.GenericSetup.zcml.cleanUp."""
    registry = gs_zcml._profile_registry
    for profile_id in gs_zcml._profile_regs:
        info = registry._profile_info.pop(profile_id, None)
        if info is None:
            logger.error("Cleanup called for profile %r, unknown of registry",
                        profile_id)
        try:
            registry._profile_ids.remove(profile_id)
        except ValueError:
            pass
    gs_zcml._profile_regs = []
    gs_zcml._upgrade_registry.clear()

# now replacing any registration already done
from zope.testing.cleanup import _cleanups
for i, (f, a, kw) in enumerate(_cleanups):
    if f is gs_zcml.cleanUp:
        _cleanups[i] = (cleanUp, a, kw)

# monkey patching for future registrations
gs_zcml.cleanUp = cleanUp


def is_verbose_security_role(role):
    """True if the given role is one of those added by verbose-security."""
    return role.startswith('_') and role.endswith('_Permission')

def verbose_security_roles_clean(roles):
    """Clean roles list in place of permission roles added by verbose-security.

    Quite inefficient, but that does not matter for our usage.
    """
    unwanted = [r for r in roles if is_verbose_security_role(r)]
    for u in unwanted:
        roles.remove(u)

