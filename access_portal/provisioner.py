import os
import re
import secrets
import ssl

from config import ACCESS_LEVELS, AURORA, DEPARTMENTS, SCOPES, scope_slug

PASSWORD_TOKEN = "{PASSWORD}"
CA_FILE = os.path.join(os.path.dirname(__file__), "global-bundle.pem")

_IDENT = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def _ident(value: str) -> str:
    if not _IDENT.match(value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


def build_grant_sql(req: dict, new_user: bool = True) -> list[str]:
    user, group, db = _ident(req["target_user"]), _ident(req["db_group"]), _ident(req["database_name"])
    privs = ", ".join(ACCESS_LEVELS[req["access_level"]][1])
    sql = []
    if new_user:
        sql.append(f"CREATE USER '{user}'@'%' IDENTIFIED BY '{PASSWORD_TOKEN}' PASSWORD EXPIRE;")
    sql.append(f"CREATE ROLE IF NOT EXISTS '{group}';")
    scope = req.get("scope", "National")
    if scope not in SCOPES:
        raise ValueError(f"Invalid scope: {scope!r}")
    if scope == "National":
        for t in req["tables"] or ["*"]:
            sql.append(f"GRANT {privs} ON `{db}`.{'*' if t == '*' else '`' + _ident(t) + '`'} TO '{group}';")
    else:
        # MySQL has no native row-level security, so the role gets a section-filtered view per table.
        all_tables = next(d["databases"][db] for d in DEPARTMENTS.values() if db in d["databases"])
        for t in req["tables"] or all_tables:
            view = f"v_{_ident(t)}_{scope_slug(scope)}"
            sql.append(f"CREATE OR REPLACE SQL SECURITY DEFINER VIEW `{db}`.`{view}` AS "
                       f"SELECT * FROM `{db}`.`{t}` WHERE section = '{scope}';")
            sql.append(f"GRANT {privs} ON `{db}`.`{view}` TO '{group}';")
    sql += [f"GRANT '{group}' TO '{user}'@'%';", f"SET DEFAULT ROLE '{group}' TO '{user}'@'%';"]
    return sql


def build_revoke_sql(req: dict) -> list[str]:
    user, group = _ident(req["target_user"]), _ident(req["db_group"])
    return [f"REVOKE '{group}' FROM '{user}'@'%';"]


def _connect():
    import pymysql

    ctx = ssl.create_default_context()
    if os.path.exists(CA_FILE):
        ctx.load_verify_locations(CA_FILE)
    else:
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    return pymysql.connect(host=AURORA["host"], port=AURORA["port"], user=AURORA["user"],
                           password=AURORA["password"], ssl=ctx, autocommit=True, connect_timeout=10)


def live_grants(username: str) -> list[str]:
    """Current grants for a user straight from Aurora (empty in dry-run mode)."""
    if not AURORA["host"]:
        return []
    c = _connect()
    try:
        with c.cursor() as cur:
            user = _ident(username)
            cur.execute(f"SHOW GRANTS FOR '{user}'@'%'")
            rows = [r[0] for r in cur.fetchall()]
            roles = _roles(rows)
            if roles:
                cur.execute(f"SHOW GRANTS FOR '{user}'@'%' USING " + ", ".join(f"'{g}'" for g in roles))
                rows += [r[0] for r in cur.fetchall()]
            return rows
    finally:
        c.close()


def _roles(grants: list[str]) -> list[str]:
    return [m for g in grants for m in re.findall(r"^GRANT `([\w.\-]+)`@`%` TO", g)]


def provision(req: dict) -> tuple[str, list[str], str | None]:
    """Returns (mode, statements for the log, one-time password if a new user was created)."""
    if not AURORA["host"]:
        return "dry-run", build_grant_sql(req), None
    c = _connect()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT 1 FROM mysql.user WHERE User=%s AND Host='%%'", (_ident(req["target_user"]),))
            new_user = cur.fetchone() is None
            stmts = build_grant_sql(req, new_user)
            password = secrets.token_urlsafe(14) if new_user else None
            for s in stmts:
                cur.execute(s.replace(PASSWORD_TOKEN, password) if password else s)
    finally:
        c.close()
    return "executed", stmts, password


def execute(statements: list[str]) -> str:
    """Runs statements on Aurora, or returns 'dry-run' when no connection is configured."""
    if not AURORA["host"]:
        return "dry-run"
    c = _connect()
    try:
        with c.cursor() as cur:
            for s in statements:
                cur.execute(s)
    finally:
        c.close()
    return "executed"
