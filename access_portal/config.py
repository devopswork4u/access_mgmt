import os
import re

# Every table has a `section` column, which is used for row-level scoping (via filtered views).
DEPARTMENTS = {
    "Tournament Operations": {
        "owner": "ops.owner",
        "databases": {"usta_tournaments": ["tournaments", "matches", "venues"]},
    },
    "Membership & Participation": {
        "owner": "member.owner",
        "databases": {"usta_membership": ["members", "clubs", "memberships"]},
    },
    "Player Development": {
        "owner": "dev.owner",
        "databases": {"usta_player_dev": ["players", "coaches", "rankings"]},
    },
}

SCOPES = ["National", "Southern", "Texas", "Midwest", "Eastern", "Northern California", "Pacific Northwest"]

ACCESS_LEVELS = {
    "Read": ("ro", ["SELECT"]),
    "Read/Write": ("rw", ["SELECT", "INSERT", "UPDATE", "DELETE"]),
    "Admin": ("admin", ["ALL PRIVILEGES"]),
}

# username -> (display name, role, department the approver owns)
USERS = {
    "jordan.reed": ("Jordan Reed (Tournament Ops Manager)", "requester", None),
    "casey.mills": ("Casey Mills (Membership Program Manager)", "requester", None),
    "ops.owner": ("Alex Rivera (Tournament Operations Data Owner)", "approver", "Tournament Operations"),
    "member.owner": ("Dana Whitfield (Membership Data Owner)", "approver", "Membership & Participation"),
    "dev.owner": ("Chris Okafor (Player Development Data Owner)", "approver", "Player Development"),
    "admin": ("Platform Admin / DBA", "admin", None),
}

DB_PATH = os.getenv("PORTAL_DB", "portal.db")

# Set AURORA_HOST="" to force dry-run mode (SQL is recorded, not executed).
AURORA = {
    "host": os.getenv("AURORA_HOST", "usta-demo.cn6iyswcclyj.us-east-2.rds.amazonaws.com"),
    "port": int(os.getenv("AURORA_PORT", "3306")),
    "user": os.getenv("AURORA_ADMIN_USER"),
    "password": os.getenv("AURORA_ADMIN_PASSWORD"),
}


def scope_slug(scope: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", scope.lower()).strip("_")


def group_name(database: str, level: str, scope: str = "National") -> str:
    base = f"{database}_{ACCESS_LEVELS[level][0]}"
    return base if scope == "National" else f"{base}_{scope_slug(scope)}"
