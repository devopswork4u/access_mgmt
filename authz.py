def database_username_from_claims(claims):
    username = claims.get("preferred_username") or claims.get("email")
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Your sign-in must provide a preferred username or email address.")
    username = username.strip()
    if "@" in username:
        username = username.partition("@")[0]
    return username.lower()


def normalize_roles(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(group.strip() for group in value if isinstance(group, str) and group.strip())


def permissions_for_roles(user_roles, authorization):
    roles = normalize_roles(user_roles)
    admin_roles = normalize_roles(authorization.get("admin_roles", ()))
    requester_roles = normalize_roles(authorization.get("requester_roles", ()))
    approver_roles = authorization.get("approver_roles", {})
    is_admin = bool(roles & admin_roles)
    approver_departments = set(approver_roles) if is_admin else {
        department
        for department, role in approver_roles.items()
        if isinstance(role, str) and role.strip() in roles
    }
    return {
        "is_admin": is_admin,
        "can_request": bool(roles & requester_roles),
        "approver_departments": frozenset(approver_departments),
    }