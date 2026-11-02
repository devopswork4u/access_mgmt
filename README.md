# USTA Data Access Management Portal

Role-based access management for USTA data in Aurora MySQL, built with Python and Streamlit. Users sign in with Microsoft Entra ID; portal permissions come from signed app-role claims.

## Authentication setup

The portal uses Streamlit's built-in OIDC support directly with a Microsoft Entra app registration. Cognito and IAM Identity Center are not required. In **App registrations**, register the portal as a single-tenant web app and add this local redirect URI:

```text
http://localhost:8501/oauth2callback
```

Create five app roles with allowed member types **Users/Groups** (not Applications): `Portal.Admin`, `Portal.Requester`, `Approver.TournamentOperations`, `Approver.Membership`, and `Approver.PlayerDevelopment`. Assign users or Entra groups to these roles in the portal's **Enterprise application**. Entra includes assigned app roles in the signed `roles` claim.

The OIDC discovery URL for your tenant is `https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration`. In `.streamlit/secrets.toml`, `client_id` must be the app registration's **Application (client) ID**, not its Object ID. The portal uses `preferred_username` for the database username when present, otherwise the email local part; ensure it is unique and MySQL-safe (letters, digits, underscore, period, or hyphen; maximum 64 characters).

Create the local settings file from the non-secret template:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Replace the example tenant/client IDs and client secret locally. Generate a long random `cookie_secret`. `.streamlit/secrets.toml` is git-ignored; never commit it or share the client secret.

The `[authorization]` section maps Entra app-role values to portal capabilities:

- `Portal.Admin` grants portal administration and approval access across all departments, plus all-request and audit views.
- `Portal.Requester` grants permission to submit and track requests.
- `Approver.TournamentOperations` approves and reviews Tournament Operations requests.
- `Approver.Membership` approves and reviews Membership & Participation requests.
- `Approver.PlayerDevelopment` approves and reviews Player Development requests.

Users without one of these assigned app roles are denied portal access. Each request is routed to its department's configured approver role. The approval audit log records the authenticated person's email (or stable subject), while the request stores the role used for authorization.

## Example users and group assignments

Use workforce users in your Microsoft Entra tenant. These fictional `example.com` accounts illustrate app-role assignments; do not use them as real credentials.

| Entra username | Display name | Email | Entra app role(s) |
|---|---|---|---|
| `elena.rios` | Elena Rios | `elena.rios@example.com` | `Portal.Admin`, `Portal.Requester` |
| `marcus.chen` | Marcus Chen | `marcus.chen@example.com` | `Portal.Requester` |
| `nina.patel` | Nina Patel | `nina.patel@example.com` | `Approver.TournamentOperations` |
| `daniel.brooks` | Daniel Brooks | `daniel.brooks@example.com` | `Approver.Membership` |
| `sophia.kim` | Sophia Kim | `sophia.kim@example.com` | `Approver.PlayerDevelopment` |

Create these app roles in the Entra app registration and assign each real user or Entra group the required roles through the Enterprise application. A person who needs multiple portal capabilities must receive each role; for example, the sample admin also has `Portal.Requester` so they can submit requests.

These are portal app roles, not AWS permissions: they do not grant AWS API access. Keep AWS service permissions on separate IAM roles and policies.

**Portal access is separate from database access.** `Portal.Admin` lets a person administer the portal and approve requests across departments; it does not create an Aurora login or grant MySQL privileges. When an approver approves a request, the portal's configured Aurora service account executes the SQL grant. The approver does not need personal Aurora credentials or `GRANT OPTION`. To give Elena database access herself, submit a request for her own signed-in account, choose the access level and scope, and approve it. The portal then creates or uses that MySQL account, creates the corresponding database role, and grants the role to that account. The `Admin` database access level means `ALL PRIVILEGES` on the requested database objects; it is not Aurora server administration.

## Start the portal

On macOS/Linux, start from the project root:

```bash
./startup.sh
```

`startup.sh` installs the requirements and starts in dry-run mode by default. The portal opens at http://localhost:8501; generated SQL is recorded but not executed, and the script does not prompt for Aurora credentials or test an Aurora connection. The Windows `startup.bat` launcher is unchanged and still expects an Aurora connection.

For live provisioning, explicitly set `AURORA_HOST`, `AURORA_PORT`, `AURORA_ADMIN_USER`, and `AURORA_ADMIN_PASSWORD` in your shell before starting. The script will not prompt for the password. The Aurora security group must allow MySQL traffic from the host running the portal, and the admin account must have the privileges needed to create users, roles, views, and grants. Use `./startup.sh --setup` only when intentionally creating the sample databases on that live Aurora instance.

## Portal workflow

1. A user in the Entra tenant signs in and submits a request. The Aurora MySQL username field defaults from the signed-in identity but can be edited to name the MySQL account that should receive access. The app validates its format, but does not look it up in Entra; the approver must verify the target username. The requester then selects a data department, database, access level, row scope, tables, duration, and business justification.
2. The request is routed to the configured approver app role for that department.
3. An authorized approver reviews the request and SQL preview, then approves or rejects it. A successful approval provisions access when Aurora is configured.
4. The signed-in Entra identity is recorded as the requester, while the manually entered MySQL username is the grant target. Requesters can review their submissions. Approvers can review access for their departments; administrators can approve across departments and review all requests, audit events, groups, and roles.

The supported scopes include `National` and the USTA sections configured in the app. A non-national scope provisions a filtered view for the selected section.

## Troubleshooting

| Problem | Fix |
|---|---|
| Sign-in configuration error | Create `.streamlit/secrets.toml` from the example and verify the Entra tenant ID, Application (client) ID, discovery URL, callback URL, and client secret. |
| Signed in but denied | Confirm the Entra ID token contains the app role in `roles` and that it matches `[authorization]`. |
| Approval queue is empty | Confirm the signed-in user or group has the department approver app role assigned in the Enterprise application. |
| Connection timeout | Check Aurora network access and whether the current network permits TCP 3306. |
| Request shows `Failed` | Inspect the Audit Log and verify the Aurora account's privileges and target database. |
