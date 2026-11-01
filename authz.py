def normalize_groups(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(group.strip() for group in value if isinstance(group, str) and group.strip())


def permissions_for_groups(user_groups, authorization):
    groups = normalize_groups(user_groups)
    admin_groups = normalize_groups(authorization.get("admin_groups", ()))
    requester_groups = normalize_groups(authorization.get("requester_groups", ()))
    approver_groups = authorization.get("approver_groups", {})
    approver_departments = {
        department
        for department, group in approver_groups.items()
        if isinstance(group, str) and group.strip() in groups
    }
    return {
        "is_admin": bool(groups & admin_groups),
        "can_request": bool(groups & requester_groups),
        "approver_departments": frozenset(approver_departments),
    }