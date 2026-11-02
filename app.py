from datetime import date, timedelta

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

import provisioner
import store
from authz import database_username_from_claims, normalize_roles, permissions_for_roles
from config import ACCESS_LEVELS, AURORA, DEPARTMENTS, SCOPES, group_name

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


# ---------- Authentication / authorization ----------
try:
    auth_settings = st.secrets["auth"]
    authorization = st.secrets["authorization"]
except (StreamlitSecretNotFoundError, KeyError):
    st.error("Authentication is not configured. Create `.streamlit/secrets.toml` from the example file.")
    st.stop()

if not st.user.is_logged_in:
    st.title("USTA Data Access")
    st.write("Sign in with your organization account to continue.")
    st.button("Sign in", on_click=st.login, type="primary")
    st.stop()

claims = st.user.to_dict()
actor = claims.get("email") or claims.get("preferred_username") or claims.get("sub")
display_name = claims.get("name") or actor
if not actor:
    st.error("Your identity provider did not return an email, preferred username, or subject claim.")
    st.stop()

try:
    default_database_username = database_username_from_claims(claims)
except ValueError:
    default_database_username = ""

user_roles = normalize_roles(claims.get("roles", []))
permissions = permissions_for_roles(user_roles, authorization)
approver_roles = authorization.get("approver_roles", {})
my_approver_departments = sorted(permissions["approver_departments"])
is_admin = permissions["is_admin"]
if not (is_admin or permissions["can_request"] or permissions["approver_departments"]):
    st.error("Your account is signed in, but it is not assigned to a portal access group.")
    st.stop()

# ---------- Sidebar / navigation ----------
with st.sidebar:
    st.title("USTA Data Access")
    st.caption("Role-based access management for USTA data in Aurora MySQL")
    st.caption(f"Signed in as **{display_name}**")
    roles = []
    if is_admin:
        roles.append("admin")
    if permissions["can_request"]:
        roles.append("requester")
    if permissions["approver_departments"]:
        roles.append("approver")
    st.caption("Role: **" + ", ".join(roles) + "**")
    st.caption("Provisioning mode: " + ("**LIVE (Aurora)**" if AURORA["host"] else "**Dry-run**"))
    pages = ["Dashboard", "User Access Lookup"]
    if permissions["can_request"]:
        pages.extend(["New Request", "My Requests"])
    if permissions["approver_departments"]:
        pages.extend(["Approval Queue", "Access Review"])
    if is_admin:
        pages.extend(["All Requests", "Groups & Roles", "Audit Log"])
    page = st.radio("Navigate", pages)
    st.button("Sign out", on_click=st.logout)

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
        target_user = c1.text_input(
            "Aurora MySQL username to receive access",
            value=default_database_username,
            help="Enter the MySQL login name that should receive the approved access.",
        )
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
            if not target_user.strip() or not just.strip():
                st.error("Aurora MySQL username and business justification are required.")
            else:
                try:
                    target_user = provisioner._ident(target_user.strip())
                    grp = group_name(db, level, req_scope)
                    approver_role = approver_roles.get(dept)
                    if not approver_role:
                        raise ValueError(f"No approver role is configured for {dept}.")
                    rid = store.create_request(dict(
                        requestor=actor, target_user=target_user, department=dept, database_name=db,
                        db_group=grp, tables=tables, access_level=level, justification=just.strip(),
                        scope=req_scope, duration=duration, expiry=str(expiry) if duration == "Temporary" else None,
                        approver=approver_role))
                    st.success(f"Request #{rid} submitted for `{target_user}` and routed to the {approver_role} role.")
                except ValueError as e:
                    st.error(str(e))

elif page == "My Requests":
    mine = store.list_requests(requestor=actor)
    table(mine, COLS)
    prov = [r for r in mine if r["status"] == "Provisioned"]
    if prov:
        rid = st.selectbox("Request revocation for", [r["id"] for r in prov])
        if st.button("Request revocation"):
            store.log(actor, "REVOCATION_REQUESTED", rid, "Requester asked for revocation")
            st.success("Revocation request logged for the approver / admin.")

elif page == "Approval Queue":
    pending = store.list_requests(status="Pending", approver_departments=my_approver_departments)
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
                store.log(actor, "REQUEST_APPROVED", r["id"], comment or "No comment")
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
                store.log(actor, "REQUEST_REJECTED", r["id"], comment or "No comment")
                st.rerun()

elif page in ("All Requests", "Access Review"):
    reqs = store.list_requests() if is_admin else store.list_requests(approver_departments=my_approver_departments)
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
                store.log(actor, "ACCESS_RECERTIFIED", rid, "Access confirmed")
                st.rerun()
            if b.button("Revoke"):
                r = store.get_request(rid)
                stmts = provisioner.build_revoke_sql(r)
                provisioner.execute(stmts)
                store.update_request(rid, status="Revoked", sql_log=(r["sql_log"] or "") + "\n" + "\n".join(stmts))
                store.log(actor, "ACCESS_REVOKED", rid, f"{r['target_user']} removed from {r['db_group']}")
                st.rerun()

elif page == "Groups & Roles":
    members = store.list_requests(status="Provisioned")
    rows = []
    for dept, d in DEPARTMENTS.items():
        for db in d["databases"]:
            for lvl in ACCESS_LEVELS:
                g = group_name(db, lvl)
                rows.append({
                    "Department": dept,
                    "Database": db,
                    "Group": g,
                    "Level": lvl,
                    "Scope": "National",
                    "Approver role": approver_roles.get(dept, "-"),
                    "Members": ", ".join(m["target_user"] for m in members if m["db_group"] == g) or "-",
                })
    seen = {r["Group"] for r in rows}
    for m in members:
        if m["db_group"] not in seen:
            seen.add(m["db_group"])
            rows.append({
                "Department": m["department"],
                "Database": m["database_name"],
                "Group": m["db_group"],
                "Level": m["access_level"],
                "Scope": m["scope"],
                "Approver role": approver_roles.get(m["department"], "-"),
                "Members": ", ".join(x["target_user"] for x in members if x["db_group"] == m["db_group"]),
            })
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
            approval_actors = {
                event["request_id"]: event["actor"]
                for event in store.list_audit()
                if event["action"] == "REQUEST_APPROVED"
            }
            df = pd.DataFrame(hist)
            df["granted_by"] = df["id"].map(approval_actors)
            df = df.rename(columns={"decided_at": "granted_on"})
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
if is_admin and page == "All Requests":
    done = [r for r in store.list_requests() if r["sql_log"]]
    if done:
        rid = st.selectbox("View executed SQL for request", [r["id"] for r in done])
        st.code(store.get_request(rid)["sql_log"], language="sql")
