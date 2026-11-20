# Gmail account invitations and recovery

This increment adds Gmail SMTP delivery, pending invitations, invitation resend, password recovery and single-use password setup. Apply migration 0010 with the checked updater while Sentinel is stopped. The migration adds only the account_links table; existing accounts, passwords, sites, equipment and maintenance records are retained.

## Private server configuration

The accompanying Configure-Gmail.ps1 helper asks for the sender address, Google app password and portal URL. It writes only private .env configuration. Never paste app passwords into chat, commit them, use a regular Google password, or put them in frontend settings.

- `SENTINEL_ACCOUNT_EMAIL_ENABLED=true`
- `SENTINEL_MAIL_SENDER`: complete Gmail or Google Workspace sender address.
- `SENTINEL_MAIL_APP_PASSWORD`: Google app password (16 letters; spaces removed).
- `SENTINEL_PUBLIC_URL`: canonical HTTPS origin of the deployed portal, without a path or query.
- `SENTINEL_ALLOW_LOCAL_MAIL_LINKS=false` normally. Set true only for explicit localhost testing.
- `ALLOWED_ORIGINS` must contain the canonical portal origin. Set `COOKIE_SECURE=true` for HTTPS.

Google requires 2-Step Verification before app passwords can be created; app passwords may be unavailable under organization policies. In that case, leave account email disabled and arrange an administrator-approved sending method. OAuth and Workspace relay are not included in this increment.

Transport uses smtp.gmail.com:587, STARTTLS with certificate verification, then authentication. Official references: [Google app passwords](https://support.google.com/mail/answer/185833) and [Google SMTP settings](https://developers.google.com/workspace/gmail/imap/imap-smtp).

Localhost links work only on the computer opening them. A recipient on another computer needs a reachable HTTPS deployment; Gmail does not make the local portal public. Configuration does not send a test email automatically.

## User workflows

A company administrator assigned to every site opens Team & access → Account invitations & recovery. They choose a non-admin role and explicit sites, review the recipient and send an invitation. The account remains in the reserved invited state until its owner uses the email link and sets a password. Administrator access can be granted through the normal reviewed team workflow after activation. Existing manual account creation remains available when sending is unconfigured.

Invitation links expire after 24 hours. Reset links expire after 30 minutes. Resending revokes previous links. Account name, role, password or site changes invalidate outstanding links. Disabling a pending account blocks activation. Administrators can resend pending invitations and view recent mail status.

The sign-in page offers Forgot password. Active and unknown accounts receive the same public response. Disabled and pending accounts are not reset; pending users need a replacement invitation. Choosing a new password revokes all sessions and outstanding links; it does not automatically sign the person in.

Tokens are generated from 32 random bytes, stored only as SHA-256 hashes, omitted from API responses/audits/logs and placed in the URL fragment so they do not enter server access logs. The browser clears the token-bearing fragment while displaying the setup form. Password policy is the existing 15–128 characters and rejects the shared demo password. Validation messages never echo submitted credentials.

## Delivery and operational boundaries

Sending occurs in an in-process background task after the request commits. The database stores pending/sent/failed/used/revoked status, without message bodies or raw link tokens. Sent means Gmail accepted SMTP submission, not confirmed inbox delivery. Check Spam and mailbox rules if needed. A timeout can be ambiguous; retry by generating a replacement link rather than reusing an uncertain link.

If the process exits during delivery, a pending row may remain; use resend or a new reset request. There is no durable external delivery worker, automatic retry scheduler or inbox receipt tracking. Email status is administrator-only; the latest 50 requests are shown. Request throttles are bounded in-memory per process; a distributed limiter and perimeter controls are required for a multi-worker public rollout. Production PostgreSQL concurrency and live Gmail delivery require separate environment validation. MFA and SSO remain future increments.

The installed auto-sync helper must be updated to include `.env.example` and future source files appropriately; private `.env` and databases remain excluded. This updater pauses source auto-sync through installation/migration and restores earlier files and the database snapshot on migration failure. It resumes the prior helper after successful installation or file restoration. Configuring mail requires restarting Sentinel.
