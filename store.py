import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requestor TEXT NOT NULL, target_user TEXT NOT NULL,
                department TEXT NOT NULL, database_name TEXT NOT NULL,
                db_group TEXT NOT NULL, tables_json TEXT NOT NULL DEFAULT '[]',
                access_level TEXT NOT NULL, justification TEXT NOT NULL,
                duration TEXT NOT NULL, expiry TEXT,
                approver TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
                decision_comment TEXT, sql_log TEXT,
                created_at TEXT NOT NULL, decided_at TEXT, last_reviewed TEXT
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
                request_id INTEGER, detail TEXT
            );
            """
        )
        cols = [r[1] for r in c.execute("PRAGMA table_info(requests)")]
        if "scope" not in cols:
            c.execute("ALTER TABLE requests ADD COLUMN scope TEXT NOT NULL DEFAULT 'National'")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(actor, action, request_id=None, detail=""):
    with conn() as c:
        c.execute(
            "INSERT INTO audit(ts, actor, action, request_id, detail) VALUES (?,?,?,?,?)",
            (_now(), actor, action, request_id, detail),
        )


def create_request(r: dict) -> int:
    with conn() as c:
        cur = c.execute(
            """INSERT INTO requests(requestor, target_user, department, database_name, db_group, tables_json,
               access_level, justification, duration, expiry, approver, scope, created_at)
               VALUES (:requestor,:target_user,:department,:database_name,:db_group,:tables_json,
               :access_level,:justification,:duration,:expiry,:approver,:scope,:created_at)""",
            {**r, "tables_json": json.dumps(r["tables"]), "created_at": _now()},
        )
        rid = cur.lastrowid
    log(r["requestor"], "REQUEST_SUBMITTED", rid,
        f"{r['access_level']} on {r['database_name']} ({r['scope']}) for {r['target_user']}; routed to {r['approver']}")
    return rid


def list_requests(**filters):
    q, args = "SELECT * FROM requests", []
    approver_departments = filters.pop("approver_departments", None)
    if filters:
        q += " WHERE " + " AND ".join(f"{k}=?" for k in filters)
        args = list(filters.values())
    if approver_departments is not None:
        q += (" AND " if filters else " WHERE ")
        if approver_departments:
            q += "department IN (" + ",".join("?" for _ in approver_departments) + ")"
            args.extend(approver_departments)
        else:
            q += "0"
    with conn() as c:
        rows = [dict(r) for r in c.execute(q + " ORDER BY id DESC", args)]
    for r in rows:
        r["tables"] = json.loads(r["tables_json"])
    return rows


def get_request(rid):
    rows = [r for r in list_requests() if r["id"] == rid]
    return rows[0] if rows else None


def update_request(rid, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE requests SET {sets} WHERE id=?", [*fields.values(), rid])


def list_audit():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC")]


def now():
    return _now()
