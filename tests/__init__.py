
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

