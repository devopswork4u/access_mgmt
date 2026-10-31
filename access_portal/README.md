# USTA Data Access Management Portal - Walkthrough

Role-based access management for USTA data in Aurora MySQL, built with Python and Streamlit.

## Start the portal

Run from `access_portal`:

```bash
./startup.sh --setup   # first time: also creates the sample USTA databases (about 2,000 rows per table)
./startup.sh           # later runs
```

On Windows without Git Bash, use `startup.bat` instead. The script asks for the Aurora password (not stored), tests the connection, and starts the app at http://localhost:8501. The sidebar should show "Provisioning mode: LIVE (Aurora)".

Prerequisites:
- The Aurora internet access gateway is enabled.
- The security group allows inbound `MYSQL/Aurora` (TCP 3306) from your current IP.
- The admin user (default `admin`) can create users and roles.

To run without touching the database, set `AURORA_HOST=""` before starting. Approvals then only record the SQL.

## People in the walkthrough

| Who | Role | Purpose |
|---|---|---|
| Jordan Reed | Requester (Tournament Ops Manager) | Submits the request |
| jane.doe | Database user | New MySQL user who receives access |
| Alex Rivera | Approver (Tournament Operations Data Owner) | Approves the request |
| Admin | Platform admin | Audit log, groups and roles, revocation |

## Step 1: Submit the request as Jordan Reed

1. In the sidebar, set **Signed in as** to *Jordan Reed (Tournament Ops Manager)*.
2. Open **New Request** and fill in:
   - Data domain: `Tournament Operations`
   - Target user: `jane.doe`
   - Database: `usta_tournaments`
   - Access level: `Read`
   - Data scope: `Texas`
   - Specific tables: `matches`
   - Duration: `Permanent`
   - Business justification: for example "Texas section reporting on matches"
3. Click **Submit request**. It is routed to Alex Rivera.

## Step 2: Approve as Alex Rivera

1. Switch **Signed in as** to *Alex Rivera (Tournament Operations Data Owner)*.
2. Open **Approval Queue**, review the request and the SQL preview.
3. Click **Approve**. The portal runs on Aurora:
   - creates the user `jane.doe`
   - creates the role `usta_tournaments_ro_texas`
   - creates the view `v_matches_texas` (Texas rows only)
   - grants the role to the user
4. Copy the one-time temporary password shown in the green box. It is not shown again.

## Step 3: Verify as jane.doe

1. In MySQL Workbench, connect with the same host (SSL required), user `jane.doe` and the temporary password.
2. Set a new password when prompted, because the temporary one is expired.
3. Run:
   ```sql
   SELECT COUNT(*), MIN(section), MAX(section) FROM usta_tournaments.v_matches_texas;
   SELECT * FROM usta_tournaments.matches LIMIT 1;
   ```
   - The first query returns only `Texas` rows.
   - The second fails with access denied.

## Step 4: Review and revoke

- **User Access Lookup**: enter `jane.doe` to see who approved the access, when, and the live grants from Aurora.
- **Audit Log** (Admin): full history of every action, exportable as CSV.
- **Access Review**: recertify or revoke access. Select the request and click **Revoke**.

## Other scenarios

- Scope `National` gives access to all rows.
- Other data domains route to other approvers: Membership & Participation to Dana Whitfield, Player Development to Chris Okafor.

## Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit` not found | Use the venv: `./.venv/Scripts/python.exe -m streamlit run app.py` |
| Connection timeout | Check the security group rule for your current IP and that the gateway is enabled. A company network or VPN may block port 3306. |
| Login failed | Wrong admin user or password |
| Request shows "Failed" | The error is in the Audit Log. The admin user may lack privileges or the databases don't exist (run `./startup.sh --setup`). |
| First `streamlit run` asks for an email | Press Enter. The setting is already disabled in `.streamlit/config.toml`. |

Run `./.venv/Scripts/python.exe test_connection.py` at any time to check DNS, network and login.
