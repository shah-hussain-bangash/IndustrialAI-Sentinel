# Condition management, increment 2: saved inactive drafts

Administrators and engineers can save a named draft from the Condition rules settings, load a saved draft, preview its settings against stored snapshots, and save a new revision with a reason. Every saved revision retains its settings, author name/identity, creation time and reason. Previous revisions cannot be edited or deleted through the application. Drafts cannot be moved between equipment; create a separate draft for another asset.

All saved rules are inactive. There is no activation endpoint in this increment. Saving never changes asset limits, demonstration health scores, existing condition episodes, investigations or notification delivery. Persistence and hysteresis semantics remain those described in CONDITION_RULE_PREVIEW.md. Engineering validation, activation, continuous evaluation, routing, suppression, escalation and operational acceptance remain future work.

## Access and conflicts

Every read and write uses the current canonical equipment/site permission and administrator/engineer role. Write routes require existing session CSRF/origin protection and Idempotency-Key. Creation and revision receipts are scoped to user and endpoint. A repeated request with the same key and payload returns the original receipt, without another revision/audit event. Reusing a key for different content is rejected. A revision requires expected_version and atomically advances the head version; a stale save returns 409. Reload drafts and load the current version before reapplying a rejected change.

The browser makes one request per save and disables editing during delivery. If delivery becomes uncertain, reload drafts and inspect the latest version before saving again. A separate click after an uncertain connection uses a new request key; automatic cross-reload client retry is not provided. Rule names need not be unique; use descriptive names and inspect author/version history.

GET /api/condition-rules/drafts?asset_id=... returns at most the latest 100 drafts and a truncation indicator. POST at the same route creates a draft. POST /drafts/{id} adds a revision; GET /drafts/{id}/history returns 50 revisions at a time with next_before_version for older pages. Historical author names reflect the identity at save time. Inactive state is a fixed API property; the storage models deliberately have no activation switch yet.

## Upgrade and preservation

Migration 0012 adds condition_rules and condition_rule_revisions. Existing account, password, encrypted MFA credential, policy, reading and operational tables are not rewritten by this migration. The installer checks expected source hashes and stopped-server/schema prerequisites, pauses configured auto-sync, backs up changed application files, runs the checked SQLite upgrade with a separate database snapshot, and resumes sync. The upgrader restores its database snapshot on failure, and the installer restores application files if copying or migration fails. Private MFA keys and environment files are excluded from this update.

Keep the original private server MFA key. Database snapshots contain encrypted MFA data but not that key. This package does not resolve the postponed off-device backup work. PostgreSQL requires a separately reviewed deployment; this user installer supports SQLite only.

## Verification

Added checks cover draft creation, version history, request idempotency, stale saves, forbidden activation properties, asset immutability, role/site access, CSRF, text validation, unchanged operational records and migration preservation. Browser acceptance of the new draft controls remains pending installation. The earlier rule-preview UI was accepted on the installed application; that does not substitute for accepting draft-save behavior.
