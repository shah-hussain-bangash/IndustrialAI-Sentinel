# Administrator authenticator MFA — staged rollout

This increment adds administrator TOTP enrollment, password-plus-code sign-in, encrypted secrets, single-use backup codes and a reviewed company policy. It is a local functional increment; it does not establish production security certification or phishing resistance.

## Installation and key custody

Stop Sentinel before using Apply-AdminMfa.ps1. The installer checks source conflicts, pauses the local GitHub auto-sync helper, installs bundled Python 3.12 Windows wheels, backs up replaced source files, initializes a private encryption key and applies the backed-up 0010 → 0011 database upgrade. Existing account passwords, data and identifiers are retained. Existing sessions receive `mfa_verified=0`; no enrolled factors exist merely from installation. Policy starts optional. A failed migration restores the database snapshot and earlier application files; additional Python dependencies and a newly created private key may remain for a safe retry.

The private Fernet key defaults to `data/security/mfa.key`. `SENTINEL_MFA_KEY_FILE` can select a different private path; `SENTINEL_MFA_KEY` can supply the key through the server environment. Do not put either key material or provisioning/backup codes in chat, Git, screenshots or frontend configuration. The key creation script never prints its value and never replaces an existing key. If enrolled factors exist but the key is missing, initialization refuses to generate a replacement.

**Back up the private server key separately in approved encrypted offline or managed secret storage before enrollment.** The existing database Backup & recovery workflow does not include this private key. A restored database with enrolled factors requires the matching key. Losing it makes those encrypted authenticator secrets unusable; there is no password-reset bypass. Key rotation and external key-management integration are future work. On Windows, keep the project/data folder accessible only to the authorized server user and administrators; managed service identity and ACL hardening remain deployment responsibilities.

## Enrollment

Sign in to one administrator account at a time. Set a personal password in Workspace settings → Account & password first; shared demo passwords cannot enroll MFA. Then open Workspace settings → Administrator MFA. Confirm the current password, scan the private QR code in Google Authenticator or Microsoft Authenticator, and submit a fresh six-digit code. A manual Base32 key is available if scanning is unavailable. Setup expires after 10 minutes; beginning setup again replaces the pending secret.

Successful confirmation activates MFA for that account immediately, preserves and marks the current session as verified and revokes its other sessions. Ten random 128-bit backup codes are shown once. Save them privately, acknowledge saving and close the display. They are stored only as hashes. Browser refresh or closing the page discards their cleartext display; a verified user can replace all codes using their password and a fresh authenticator or unused backup code.

## Sign-in and recovery

An enrolled account always requires password plus authenticator or an unused backup code, even while company rollout is optional. A valid password creates only a five-minute, HttpOnly, SameSite-strict challenge cookie. It does not grant workspace access. The verification request is additionally bound to a challenge CSRF token. A full session is issued only after successful second-factor verification. Challenges are single-use, limited to five attempts and invalidated by account password/role/site changes. Replay-resistant code consumption uses an optimistic database version.

TOTP uses SHA-1, six digits and a 30-second step with one adjacent step of clock tolerance. Keep the phone and server clocks accurate. A code that was just used to enroll cannot be reused for sign-in; wait for a fresh code or use a backup code. Backup codes are one-use and cannot be replayed across sessions. A password reset revokes sessions but does not remove MFA. Demoting an enrolled administrator does not silently remove their existing second factor; factor-management UI is currently administrator-scoped.

If the company requirement is off, removing one's authenticator requires current password plus a valid factor and revokes all sessions. When the company requirement is on, removal is blocked. Instead, sign in using a backup code, choose Replace lost authenticator and prove the password plus another unused code. The old factor and sessions are revoked. Password sign-in then grants enrollment-only access until the new factor is confirmed; the company policy remains on.

If both the device and all backup codes are lost, normal sign-in cannot recover the account. Use another enrolled full-company administrator for operational continuity and follow a separately approved identity-verification recovery procedure. This increment deliberately includes no unaudited administrator bypass or email-only MFA removal. A reviewed, independently verified recovery support workflow remains a production requirement.

## Company rollout

Only a full-company administrator with an enrolled authenticator can change policy. Every currently active administrator must enroll before the company requirement can be enabled. The policy change requires current password, a fresh factor and an explicit review confirmation. Once enabled, a newly promoted administrator without a factor is restricted to enrollment and sign-out until enrollment completes. People using the shared demo password cannot be promoted under the required policy; they must set a personal password first. Regular roles do not acquire a new MFA requirement in this increment.

Do not test different accounts in ordinary tabs of the same browser profile: session cookies are shared. Use a separate browser/profile or an independent private session. Existing in-flight requests are not retrospectively cancelled when access changes.

## Verification and limits

Backend verification includes the RFC 6238 SHA-1 test vectors (including post-2038 timestamps), no-access-before-second-factor, replay rejection, backup-code hashing and single use, challenge expiry/attempt/CSRF controls, disable handling, policy rollout, mandatory enrollment gates, factor replacement and missing-key failures. Installer rehearsals cover existing-data preservation and rollback. Real phone scanning is a user acceptance step; no real administrator was enrolled or policy enabled during development.

This implementation uses in-process bounded request throttles plus persistent per-challenge attempt counters. Distributed rate limiting, phishing-resistant passkeys/WebAuthn, risk-based policy, security-event notification delivery, monitored key management and an independently reviewed lost-all-factors process remain production hardening work. TOTP is not phishing resistant.

References: [RFC 6238](https://www.rfc-editor.org/rfc/rfc6238), [NIST authenticator guidance](https://pages.nist.gov/800-63-4/sp800-63b/authenticators/) and [Fernet key custody](https://cryptography.io/en/stable/fernet/).
