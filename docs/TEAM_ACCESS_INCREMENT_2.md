# Team and site access — foundation increment 2

Team & access (`#team`) adds account creation, role/site assignment, disable/reactivate, session revocation and audit evidence. Uses the existing revision 0009 database tables; no schema migration or existing account changes occur at installation.

Only an administrator with membership of every current site can list or manage the team. Other roles and scoped administrators receive a server-side 403. Roles are global across a member's selected sites: admin, engineer, approver, planner, technician and observer. These retain the application's existing route permissions; this is not a new granular role-policy engine. Disabled accounts use the reserved `disabled` role; choose an active role to reactivate.

Account creation requires a distinct email, an explicit role, at least one existing site and a 15–128 character password different from the demo password. Passwords are stored using the existing salted password hashing scheme. No invitation email is sent. Share initial credentials through an approved private channel and have the person change their password in Account settings. Forced first-login password change, verified invitations, reset links, MFA, SSO and external identity-provider support remain future increments.

Access changes revoke all of the target's current browser sessions. Disabled accounts are rejected by sign-in and session authentication and excluded from demo account choices. Existing gateway credentials are independent device credentials and require separate gateway revocation if needed. Already-running requests are not retrospectively cancelled.

An administrator cannot change their own role, site assignments or name here. This preserves the acting administrator's access. A second full-company administrator must make any such change. Company configuration writes serialize through the organization revision; account edits additionally require an opaque version token. A stale form returns 409 rather than overwriting newer account settings. No hard deletion of users or their history is provided.

Before/after role and site changes are audited against affected sites. Passwords, password hashes and version tokens are excluded from audit details. Membership checks use canonical site IDs. Existing company profile, equipment, sensor data and documents remain intact.

This is a tested local functional increment, not a certification of end-to-end production readiness. Production rollout still requires identity hardening, HTTPS deployment, validated PostgreSQL concurrency, operational monitoring and recovery drills.

Installation pauses the local auto-sync helper while files are replaced, checks existing source hashes, backs up replaced files and restores them if copying fails. The previous auto-sync helper is resumed afterward when it was running. Restart Sentinel to load the backend changes, refresh the browser and open Team & access as a full-company administrator. Team/account data stays in the ignored local database and is not uploaded to GitHub.
