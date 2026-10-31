from datetime import date, timedelta

import pandas as pd
import streamlit as st

import provisioner
import store
from config import ACCESS_LEVELS, AURORA, DEPARTMENTS, SCOPES, USERS, group_name

st.set_page_config(page_title="USTA Data Access Management", page_icon=":tennis:", layout="wide")
store.init()

STATUS_ICON = {"Pending": "🟠", "Provisioned": "🟢", "Rejected": "🔴", "Revoked": "⚫", "Failed": "❌"}


def table(rows, cols):
    if not rows:
        st.info("Nothing to show.")
        return
    df = pd.DataFrame(rows)
    df["status"] = df["status"].map(lambda s: f"{STATUS_ICON.get(s, '')} {s}")
    df["tables"] = df["tables"].map(lambda t: ", ".join(t) or "All")
    st.dataframe(df[cols], use_container_width=True, hide_index=True)


COLS = ["id", "target_user", "department", "database_name", "scope", "access_level", "db_group", "tables",
        "duration", "expiry", "approver", "status", "created_at"]


# ---------- Sidebar / login ----------
with st.sidebar:
    st.title("USTA Data Access")
    st.caption("Role-based access management for USTA data in Aurora MySQL")
    me = st.selectbox("Signed in as", list(USERS), format_func=lambda u: USERS[u][0])
    name, role, owned_dept = USERS[me]
    st.caption(f"Role: **{role}**" + (f" | Owns: **{owned_dept}**" if owned_dept else ""))
    st.caption("Provisioning mode: " + ("**LIVE (Aurora)**" if AURORA["host"] else "**Dry-run**"))
    pages = {
        "requester": ["Dashboard", "New Request", "My Requests", "User Access Lookup"],
        "approver": ["Dashboard", "Approval Queue", "Access Review", "User Access Lookup"],
        "admin": ["Dashboard", "All Requests", "Groups & Roles", "Access Review", "User Access Lookup", "Audit Log"],
    }[role]
    page = st.radio("Navigate", pages)

st.header(page)

# ---------- Pages ----------
if page == "Dashboard":
    reqs = store.list_requests()
    cols = st.columns(4)
    for col, s in zip(cols, ["Pending", "Provisioned", "Rejected", "Revoked"]):
        col.metric(f"{STATUS_ICON[s]} {s}", sum(r["status"] == s for r in reqs))
    st.subheader("Recent requests")
    table(reqs[:8], COLS)
    st.graphviz_chart(
        'digraph { rankdir=LR; node [shape=box, style=rounded];'
        '"Tournament / Program Manager" -> "Access Request Portal" -> "Data Owner Approval" -> "Provisioning Service" -> "Aurora MySQL (USTA data)" -> "Audit & Reporting"; }'
    )

elif page == "New Request":
    dept = st.selectbox("Data domain", list(DEPARTMENTS))
    dbs = DEPARTMENTS[dept]["databases"]
    with st.form("request"):
        c1, c2 = st.columns(2)
        target = c1.text_input("Target user", placeholder="e.g. jane.doe")
        db = c2.selectbox("Database", list(dbs))
        level = c1.selectbox("Access level", list(ACCESS_LEVELS))
        req_scope = c2.selectbox("Data scope (USTA section)", SCOPES,
                                 help="National = all rows. A section limits the user to rows for that section only.")
        tables = st.multiselect("Specific tables (empty = all tables in the database)", dbs[db])
        c3, c4 = st.columns(2)
        duration = c3.radio("Duration", ["Permanent", "Temporary"], horizontal=True)
        expiry = c4.date_input("Expiry (temporary only)", date.today() + timedelta(days=30))
        just = st.text_area("Business justification")
        if st.form_submit_button("Submit request", type="primary"):
            if not target.strip() or not just.strip():
                st.error("Target user and justification are required.")
            else:
                try:
                    grp = group_name(db, level, req_scope)
                    provisioner._ident(target.strip())
                    rid = store.create_request(dict(
                        requestor=me, target_user=target.strip(), department=dept, database_name=db,
                        db_group=grp, tables=tables, access_level=level, justification=just.strip(),
                        scope=req_scope, duration=duration, expiry=str(expiry) if duration == "Temporary" else None,
                        approver=DEPARTMENTS[dept]["owner"]))
                    st.success(f"Request #{rid} submitted and routed to {USERS[DEPARTMENTS[dept]['owner']][0]}.")
                except ValueError as e:
                    st.error(str(e))

elif page == "My Requests":
    mine = store.list_requests(requestor=me)
    table(mine, COLS)
    prov = [r for r in mine if r["status"] == "Provisioned"]
    if prov:
        rid = st.selectbox("Request revocation for", [r["id"] for r in prov])
        if st.button("Request revocation"):
            store.log(me, "REVOCATION_REQUESTED", rid, "Requester asked for revocation")
            st.success("Revocation request logged for the approver / admin.")

elif page == "Approval Queue":
    pending = [r for r in store.list_requests(status="Pending", approver=me)]
    if "new_pw" in st.session_state:
        u, pw = st.session_state.pop("new_pw")
        st.success(f"New database user `{u}` created. One-time temporary password (shown once, must be changed at first login): `{pw}`")
    if not pending:
        st.info("No pending requests for you.")
    for r in pending:
        with st.expander(f"#{r['id']} - {r['access_level']} on {r['database_name']} ({r['scope']}) for {r['target_user']}", expanded=True):
            st.write(f"**Requested by:** {r['requestor']}  |  **Group:** `{r['db_group']}`  |  "
                     f"**Tables:** {', '.join(r['tables']) or 'All'}  |  **Duration:** {r['duration']} {r['expiry'] or ''}")
            st.write(f"**Justification:** {r['justification']}")
            st.code("\n".join(provisioner.build_grant_sql(r)), language="sql")
            comment = st.text_input("Comment", key=f"c{r['id']}")
            a, b, _ = st.columns([1, 1, 6])
            if a.button("Approve", key=f"a{r['id']}", type="primary"):
                store.log(me, "REQUEST_APPROVED", r["id"], comment or "No comment")
                try:
                    mode, stmts, password = provisioner.provision(r)
                    store.update_request(r["id"], status="Provisioned", decision_comment=comment,
                                         decided_at=store.now(), sql_log="\n".join(stmts))
                    store.log("Provisioning Service", "ACCESS_PROVISIONED", r["id"],
                              f"{len(stmts)} statements ({mode}); {r['target_user']} -> {r['db_group']}")
                    store.log("Notification Service", "USER_NOTIFIED", r["id"], f"Confirmation sent to {r['target_user']}")
                    if password:
                        st.session_state["new_pw"] = (r["target_user"], password)
                except Exception as e:
                    store.update_request(r["id"], status="Failed", decision_comment=str(e))
                    store.log("Provisioning Service", "PROVISIONING_FAILED", r["id"], str(e))
                st.rerun()
            if b.button("Reject", key=f"r{r['id']}"):
                store.update_request(r["id"], status="Rejected", decision_comment=comment, decided_at=store.now())
                store.log(me, "REQUEST_REJECTED", r["id"], comment or "No comment")
                st.rerun()

elif page in ("All Requests", "Access Review"):
    reqs = store.list_requests()
    if role == "approver":
        reqs = [r for r in reqs if r["approver"] == me]
    if page == "All Requests":
        table(reqs, COLS)
    else:
        active = [r for r in reqs if r["status"] == "Provisioned"]
        table(active, COLS + ["last_reviewed"])
        if active:
            rid = st.selectbox("Select request", [r["id"] for r in active])
            a, b, _ = st.columns([1, 1, 6])
            if a.button("Recertify", type="primary"):
                store.update_request(rid, last_reviewed=store.now())
                store.log(me, "ACCESS_RECERTIFIED", rid, "Access confirmed")
                st.rerun()
            if b.button("Revoke"):
                r = store.get_request(rid)
                stmts = provisioner.build_revoke_sql(r)
                provisioner.execute(stmts)
                store.update_request(rid, status="Revoked", sql_log=(r["sql_log"] or "") + "\n" + "\n".join(stmts))
                store.log(me, "ACCESS_REVOKED", rid, f"{r['target_user']} removed from {r['db_group']}")
                st.rerun()

elif page == "Groups & Roles":
    members = store.list_requests(status="Provisioned")
    rows = []
    for dept, d in DEPARTMENTS.items():
        for db in d["databases"]:
            for lvl in ACCESS_LEVELS:
                g = group_name(db, lvl)
                rows.append(dict(Department=dept, Database=db, Group=g, Level=lvl, Scope="National", Owner=USERS[d["owner"]][0],
                                 Members=", ".join(m["target_user"] for m in members if m["db_group"] == g) or "-"))
    seen = {r["Group"] for r in rows}
    for m in members:
        if m["db_group"] not in seen:
            seen.add(m["db_group"])
            rows.append(dict(Department=m["department"], Database=m["database_name"], Group=m["db_group"],
                             Level=m["access_level"], Scope=m["scope"], Owner=USERS[DEPARTMENTS[m["department"]]["owner"]][0],
                             Members=", ".join(x["target_user"] for x in members if x["db_group"] == m["db_group"])))
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "User Access Lookup":
    who = st.text_input("Database username", placeholder="e.g. jane.doe").strip()
    if who:
        try:
            provisioner._ident(who)
        except ValueError as e:
            st.error(str(e))
            who = ""
    if who:
        st.subheader("Access granted through the portal")
        hist = store.list_requests(target_user=who)
        if hist:
            df = pd.DataFrame(hist)
            df = df.rename(columns={"approver": "granted_by", "decided_at": "granted_on"})
            st.dataframe(df[["id", "department", "database_name", "access_level", "scope", "db_group",
                             "status", "granted_by", "granted_on", "expiry"]], use_container_width=True, hide_index=True)
        else:
            st.info("No portal requests for this user.")
        st.subheader("Current grants in Aurora")
        if not AURORA["host"]:
            st.info("Dry-run mode: Aurora is not queried.")
        else:
            try:
                grants = provisioner.live_grants(who)
                st.code("\n".join(grants) or "No grants", language="sql")
            except Exception as e:
                st.warning(f"Could not read grants (user may not exist): {e}")

elif page == "Audit Log":
    log = pd.DataFrame(store.list_audit())
    if log.empty:
        st.info("No events yet.")
    else:
        action = st.multiselect("Filter by action", sorted(log["action"].unique()))
        view = log[log["action"].isin(action)] if action else log
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.download_button("Export CSV", view.to_csv(index=False), "audit_log.csv", "text/csv")

# Request detail with executed SQL for admins
if role == "admin" and page == "All Requests":
    done = [r for r in store.list_requests() if r["sql_log"]]
    if done:
        rid = st.selectbox("View executed SQL for request", [r["id"] for r in done])
        st.code(store.get_request(rid)["sql_log"], language="sql")
