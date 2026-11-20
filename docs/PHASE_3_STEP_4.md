# Phase 3, Step 4: time-aligned event snapshots

This increment connects reviewed independent sensor events to the existing snapshot analytics. It is a local reference implementation. The 5-second alignment policy is a demonstration rule and requires equipment-specific engineering review before a plant pilot.

## Install and walkthrough

1. Stop Sentinel with Ctrl+C. Run Apply-Phase3Step4.ps1 against the existing project. It validates hashes/schema, backs up application files and SQLite, and migrates to revision 0005. Restart scripts/run.py and refresh Ctrl+F5. No dependency install or full-project replacement is required.
2. In Live monitoring, pause simulation. Otherwise its new snapshots can supersede the proposed event frame.
3. Open Sensor registry > Inspect events for any C-202 channel.
4. Select the Equipment alignment tab at the top of the inspector.
5. Existing independent events may be missing, old, misaligned or poor quality. The screen lists every blocking reason.
6. Select Create aligned test frame. Review the four canonical values (defaults: vibration 2 mm/s, temperature 70 degC, pressure 5 bar, flow 120 m3/h). Select Save four test events. This saves four manual test readings with one observation time and source manual-alignment-ui; it does not publish automatically or connect equipment.
7. Review the four rows and Ready for review & publication status. Select Publish reviewed snapshot once.
8. Inspect the snapshot receipt and Published snapshots section. Expand a record to see the four source-event IDs. Reopen the inspector to confirm history persists.
9. Close the inspector, use the workspace refresh control, and open Live monitoring for that asset. Its latest source should be Aligned sensor events. Existing condition/anomaly logic now evaluates that complete snapshot.

The original Sensor events tab preserves single-reading entry and raw-to-canonical conversion history. No previous independent event is overwritten or automatically backfilled into snapshots.

## Policy: aligned-events-v1

For each of vibration, temperature, pressure and flow, select the most recent independent event by observed_at descending, then received_at, then event UUID. A newer bad/suspect event is never silently skipped in favor of an older good event. Every channel must belong to the same asset through its registered sensor.

All four events must be present, quality good, finite, with positive observation timestamps no later than the server time, and not stale under the current sensor configuration. Raw units, canonical units, conversion version units-v1, conversion result and canonical acceptance ranges are checked again before publication. Channel observation-time spread must be at most 5 seconds.

Snapshot timestamp is the oldest source observation time. Values are canonical measurements, with no interpolation, gap filling or artificial missing-channel values. The resulting timestamp must be strictly newer than the asset's latest equipment snapshot. Ineligible frames return reasons and do not save a snapshot.

The preview signature binds exact event contents, sensor configuration, asset version and the previous latest snapshot ID. Commit recomputes the preview and rejects a changed signature with 409. Freshness is rechecked at commit even if the signature has not changed. Publish requires Engineer/Admin permissions, site access, CSRF and an idempotency key. Current asset permissions are checked before replaying a saved response.

Publishing creates one complete good-quality Reading plus a SnapshotProjection row with foreign keys to all four events, the reading, asset and actor; it records an audit event in the same transaction. A compare-and-update of asset.version serializes competing projection commits and invalidates stale asset-edit forms. Unique frame/message identities prevent duplicate publication. Failure rolls back the reading, provenance, version update and audit. A same-key replay returns the original receipt. Condition episode checks run only when the snapshot is current. Normal condition rules do not automatically close existing episodes.

The simulation and existing snapshot ingestion APIs remain independent writers. Pause simulation during manual tests. Later snapshots can legitimately replace an aligned snapshot as the latest; saved provenance remains in history. Production ordering, synchronized device clocks and a durable streaming projection worker remain separate work.

## APIs

GET /api/snapshot-projections/preview?asset_id=<ID>: authorized read-only candidate, rows, reasons, ready, spread, oldest timestamp, policy and preview_signature.

POST /api/snapshot-projections with JSON {"asset_id":"<ID>","preview_signature":"<64-character SHA256>"}: creates a reviewed eligible snapshot. Use authenticated session, X-CSRF-Token and Idempotency-Key. Returns reading_id, event_ids, timestamp, canonical values and policy. 422 means ineligible frame/input; 409 means changed preview or conflict; 403/404 enforce role/site boundaries.

GET /api/snapshot-projections/history?asset_id=<ID>: latest 20 published records with source-event IDs. The event history API remains available for original/raw measurements. There is no automatic publishing, event mutation, plant control, vendor connection or new LLM integration.

## Verified scope

107 tests pass on SQLite and the same 107 on isolated native PostgreSQL 18.6 with a non-superuser runtime role. Tests cover complete-frame analytics, unit conversion, missing/bad/suspect/stale/future readings, misalignment, oldest-time selection, outdated previews/configuration/snapshots, duplicate/replayed commits, site permissions, CSRF, rollback, stored-data validation and upgrade preservation. Alembic fresh/legacy migrations and metadata checks pass. A PostgreSQL logical dump/restore preserved the tested runtime readings, sensor events and published projection rows.

TypeScript and Vite production build pass. Interactive browser verification of this increment was not performed because local browser access was disabled in Work settings. The operator walkthrough above remains the installed-app acceptance check. One existing Starlette test-client deprecation warning remains. No production throughput, broker, plant integration, deployment or industrial-model accuracy is claimed.

## Remaining work

Phase 3 remains partial: quarantine/reprocessing, retention and partitioning, durable streaming ingestion, device identity, equipment-specific alignment policy, live PostgreSQL cutover and production capacity/recovery validation. Subsequent phases still include evaluated ML/RAG, vendor integrations, enterprise identity and operational pilot acceptance.
