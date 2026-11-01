# USTA Data Access Management Portal

Role-based access management for USTA data in Aurora MySQL, built with Python and Streamlit. Users sign in through an OIDC identity provider; portal permissions come only from signed group claims.

## Authentication setup

The portal uses Streamlit's built-in OIDC support with a Cognito user pool as the OIDC provider. Configure IAM Identity Center as a federated identity provider for that Cognito pool. Streamlit's local callback URL is:

```text
http://localhost:8501/oauth2callback
```

In the Cognito app client, allow this callback URL and request the `openid`, `email`, and `profile` scopes. Use the user pool's OIDC discovery URL as `server_metadata_url`. The Cognito ID token must include a stable identity claim (`email`, `preferred_username`, or `sub`) and the `cognito:groups` claim.

Create the local settings file from the non-secret template:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Replace the example Cognito values and group names. `cookie_secret` must be a long, random value. `.streamlit/secrets.toml` is git-ignored; do not commit it or share its client secret.

The `[authorization]` section maps Cognito groups to portal capabilities:

- `usta-portal-admins` grants administrator access to all requests and audit functions.
- `usta-portal-requesters` grants permission to submit and track requests.
- `usta-tournament-approvers` approves and reviews Tournament Operations requests.
- `usta-membership-approvers` approves and reviews Membership & Participation requests.
- `usta-player-development-approvers` approves and reviews Player Development requests.

Users without one of these configured group memberships are denied portal access. Each request is routed to its department's configured approver group. The approval audit log records the authenticated person's email (or stable subject), while the request stores the group used for authorization.

**Group synchronization:** IAM Identity Center groups are not automatically copied into Cognito user-pool groups. Cognito's `cognito:groups` claim reflects Cognito group membership. Until an explicit synchronization path is configured, an administrator must maintain the Cognito groups and membership used by this portal. Do not treat Identity Center groups as effective portal roles unless that synchronization has been verified.

## Example users and group assignments

Create workforce users in **IAM Identity Center** (or your connected workforce directory), not as traditional AWS IAM users. These fictional `example.com` accounts illustrate the portal group assignments; do not use them as real credentials.

| Identity Center username | Display name | Email | Identity Center group(s) and matching Cognito group(s) |
|---|---|---|---|
| `portal.admin` | Avery Example | `portal.admin@example.com` | `usta-portal-admins`, `usta-portal-requesters` |
| `portal.requester` | Morgan Sample | `portal.requester@example.com` | `usta-portal-requesters` |
| `tournament.approver` | Taylor Demo | `tournament.approver@example.com` | `usta-tournament-approvers` |
| `membership.approver` | Jamie Sample | `membership.approver@example.com` | `usta-membership-approvers` |
| `playerdev.approver` | Casey Demo | `playerdev.approver@example.com` | `usta-player-development-approvers` |

Create the five groups in IAM Identity Center and assign these users as shown. Also create the same-named groups in the Cognito user pool and ensure each federated user's Cognito group membership is maintained or synchronized; the portal authorizes from Cognito's `cognito:groups` token claim. A user who needs multiple portal capabilities must belong to each corresponding group. For example, the sample admin is also in the requester group so they can submit requests.

These are portal authorization groups, not AWS permission groups: they do not grant AWS API access. Keep AWS service permissions on separate IAM roles and policies.

## Start the portal

From the project root, install requirements and start Streamlit:

```bash
python -m pip install -r requirements.txt
./startup.sh
```

On Windows, use `startup.bat`. The portal opens at http://localhost:8501. For local development, set `AURORA_HOST=""` to run approvals in dry-run mode; generated SQL is recorded but not executed.

For live provisioning, configure `AURORA_HOST`, `AURORA_PORT`, `AURORA_ADMIN_USER`, and `AURORA_ADMIN_PASSWORD`. The Aurora security group must allow MySQL traffic from the host running the portal, and the admin account must have the privileges needed to create users, roles, views, and grants.

## Portal workflow

1. A requester signs in, submits a request, and selects a data department, database, access level, row scope, tables, duration, and business justification.
2. The request is routed to the configured approver group for that department.
3. An authorized approver reviews the request and SQL preview, then approves or rejects it. A successful approval provisions access when Aurora is configured.
4. Requesters can review their submissions. Approvers can review access for their departments; administrators can review all requests, audit events, groups, and roles.

The supported scopes include `National` and the USTA sections configured in the app. A non-national scope provisions a filtered view for the selected section.

## Troubleshooting

| Problem | Fix |
|---|---|
| Sign-in configuration error | Create `.streamlit/secrets.toml` from the example and verify the Cognito app client, discovery URL, callback URL, and client secret. |
| Signed in but denied | Confirm the Cognito ID token contains `cognito:groups` and that the user's groups match the names in `[authorization]`. |
| Approval queue is empty | Confirm the request's department is mapped to a Cognito group containing the signed-in user. |
| Connection timeout | Check Aurora network access and whether the current network permits TCP 3306. |
| Request shows `Failed` | Inspect the Audit Log and verify the Aurora account's privileges and target database. |
