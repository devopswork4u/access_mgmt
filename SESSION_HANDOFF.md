# Session Handoff: Access Management Portal

## Current project
- Project path: `/Users/rahulsharma/Desktop/Projects/TGS/access_mgmt` (terminal cwd). The VS Code workspace listing may show a different repository.
- The user is switching sessions and asked to preserve the task context.

## Completed
- Fixed the Python 3.9 import-time error in `provisioner.py` by adding `from __future__ import annotations` for the `str | None` return annotation.
- Verified `provisioner` imports with the project's Python 3.9 venv. The user later reported `./startup.sh` exited with code 0.
- Streamlit in the project venv is 1.50.0 and exposes `st.login`.

## Requested feature and agreed direction
- Replace the fake `Signed in as` user dropdown with real AWS-backed authentication.
- User chose IAM Identity Center for workforce identity and local Streamlit during development.
- User approved a Cognito OIDC user pool federated to IAM Identity Center as the login bridge.
- Use signed token group claims to determine portal permissions; never let users select their own role.
- Do not use IAM user access keys or passwords for human web-app login.

## Important architecture caveat
- Streamlit supports OIDC through `st.login()` / `st.user`.
- IAM Identity Center custom applications use SAML or OAuth trusted identity propagation; it is not a drop-in generic OIDC provider for Streamlit.
- Cognito user-pool groups appear in the `cognito:groups` token claim, but Cognito group membership is not automatically synchronized from Identity Center. Before claiming Identity Center groups drive roles, configure a trusted group claim/synchronization path, or explicitly document Cognito groups as separately administered. Never silently assume the sync exists.

## Relevant existing code
- `app.py` currently selects from the hard-coded `USERS` map in `config.py`; requester, approver, and admin permissions are based on that selected identity.
- `config.py` has demo `USERS` and each department's `owner` is a demo username such as `ops.owner`.
- `store.py` persists `requestor` and `approver` as strings. Approval queue currently filters by exact approver username; this must change to support authorized group membership while preserving audit identity.
- `README.md` documents the current demo dropdown workflow and needs an auth/setup update.
- Requirements currently say `streamlit>=1.35`; built-in OIDC login requires a newer Streamlit version, so raise the minimum to the supported version when implementing.
- No authentication feature edits have been made yet.

## Next steps
1. Check `git status --short --branch` before editing; the prior worktree check was canceled, so do not assume it is clean.
2. Inspect `.gitignore` and README in the target project. Add a non-secret `.streamlit/secrets.toml.example`; never create or commit live client secrets.
3. Implement a strict login gate using `st.user.is_logged_in`, `st.login()`, and `st.logout()`. Use authenticated claims for actor identity and group-based capabilities.
4. Replace demo owner usernames with configured approver groups; make approval queue and access review authorize by group membership (admins can retain their broader permissions).
5. Document Cognito + Identity Center federation, local callback `http://localhost:8501/oauth2callback`, required claims, and the group synchronization/admin model.
6. Validate with focused tests for group-to-capability mapping and approval filtering, then run Python syntax/import checks with `.venv/bin/python`.

No AWS account resources or credentials have been configured in this repository. Do not ask the user to paste secrets into chat; use local Streamlit secrets or an AWS secret store.
