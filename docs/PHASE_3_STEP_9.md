# Phase 3, Step 9: asset-scoped telemetry gateway access

This increment adds authenticated HTTP telemetry senders for one equipment asset per credential. It remains a local reference application. It does not connect MQTT, SCADA or a PLC, attest physical devices, approve maintenance or automatically publish equipment snapshots.

## Install and verify

Prerequisite: Step 8 / schema 0007. Stop Sentinel with Ctrl+C, run Apply-Phase3Step9.ps1 against the existing project, restart scripts/run.py and refresh Ctrl+F5. The updater validates payload hashes, backs up application files and SQLite, and migrates to 0008. No credential is created during migration. Existing accounts, passwords, readings, original files, review decisions and snapshot provenance are retained.

1. Sign in as Admin. Open Workspace settings > Telemetry gateway access.
2. Select Create gateway; enter a name, select C-202 and choose the lifetime (default 7 days, allowed 1–90).
3. Select Issue scoped credential. Copy the credential privately from the once-only masked field. Reveal and Clear are available. Lost responses require rotation; credentials cannot be retrieved again.
4. Keep Sentinel running. In a second PowerShell terminal run the project Python with scripts/send_gateway_sample.py. Paste the gateway credential at its hidden prompt, not your account password. Do not paste it into a chat or command argument.
5. Expect inserted=4 and snapshot_projection=false. Refresh gateway access to see the accepted-batch time and count. Inspect the asset's four sensor event histories to see their gateway source.
6. Equipment alignment remains a separate review and publication action. Four good, fresh channel events must align within five seconds and be newer than the latest equipment snapshot. Pause simulation before testing publication.
7. Rotate a credential to invalidate its predecessor. Revoke to permanently close this gateway identity. Create a new gateway if a revoked one is needed again.

## API and identity contract

Admin management uses existing cookie authentication, CSRF/origin checks and canonical site access. Routes are GET/POST /api/gateways and POST /api/gateways/{id}/rotate or /revoke. Rotation and revocation require expected_version and a request idempotency key. List responses expose metadata only; the latest 100 accessible gateways are shown.

The credential is a cryptographically random bearer secret. Only its SHA-256 digest is retained. Plaintext is returned once, held only in UI memory, and excluded from persisted receipts and audit. Repeating an issuance or rotation request returns metadata without the secret. The UI copy action places it on the user's clipboard; clear that clipboard when finished.

GET /api/gateway-identity and POST /api/gateway-events/batches use Authorization: Bearer, without a browser account session. The latter requires Idempotency-Key and 1–500 records using the existing strict sensor event schema. Every sensor must belong to the credential's single asset. Requests are blocked after expiry, revocation, issuer role loss or loss of the issuer's canonical site access. A credential alone grants no admin, document or maintenance API access.

Atomic batches retain original values, units, observed time and conversion evidence. Invalid batches reject as a whole; they do not populate the opt-in quarantine queue. A stored source identifies the gateway UUID; audit identifies its credential version. Exact message redelivery remains deduplicated across rotation. A changed payload with the same sensor/message identity is rejected. Concurrent credential-version changes conflict safely. Accepted-batch counts measure successful new idempotency receipts: repeated same-key requests do not increment; a new-key valid duplicate batch does.

## Sender and boundaries

The bundled sender submits 2 mm/s vibration, 70 degC temperature, 5 bar pressure and 120 m3/h flow with one observation time. It prompts for the secret, does not save it, rejects redirects, allows HTTP only for loopback and requires HTTPS for remote destinations. Transport/5xx retries preserve the same request key and payload. It is a sample utility, not a durable edge spool or broker bridge.

Production work still includes managed provisioning, TLS termination, rate limits, independent security assessment, monitored deployment, broker/device identity, offline delivery, representative industrial data and operational acceptance. A source label is not proof of a physical device. No live plant, vendor CMMS, SSO, calibrated failure probability or RUL is claimed.

## Verification

172 backend tests pass on SQLite and PostgreSQL 18.6. Scope includes credential access, rotation/revocation/expiry, issuer permission changes, hash-only persistence, metadata-only receipts, duplicate handling and rollback. PostgreSQL verification uses a non-superuser runtime and logical dump/restore. TypeScript and the production frontend build pass. Interactive browser acceptance remains pending because local browser access is disabled. Installer and live local HTTP validation are recorded in docs/evidence/phase3-step9-verification.json.
