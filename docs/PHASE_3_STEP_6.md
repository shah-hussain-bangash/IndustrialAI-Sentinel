# Phase 3, Step 6: searchable paginated review queue

This increment adds scoped search, status summaries and bidirectional browsing to Data review. It removes the interface's previous latest-50-only limitation without deleting evidence. Database schema remains 0006; there is no new migration or dependency.

## Install and walkthrough

Prerequisite: Phase 3 Step 5 installed. Stop Sentinel with Ctrl+C, run Apply-Phase3Step6.ps1, restart scripts/run.py and refresh Ctrl+F5. The checked updater backs up application files and SQLite, verifies the existing schema and preserves accounts, readings, quarantine decisions and snapshot provenance. Do not apply older updaters afterward.

1. Open Sensor registry > C-202 Temperature > Inspect events > Data review.
2. Select All statuses to see existing pending, corrected and dismissed records. The counts summarize matching review statuses.
3. In Search review items enter Fahrenheit, then click Search. The previously entered correction reason should match. You may also search a review UUID, original message ID, source or decision text.
4. Click Clear search. Select Dismissed or Corrected & replayed to isolate one state.
5. At the bottom choose 10, 25 or 50 Items per page. Next is available only when more matching items exist; Previous returns to an earlier result boundary. Tests cover browsing more than 50 records; you do not need to generate extra test records just to enable the button.
6. Refresh queue includes newer submissions and starts browsing at page one. Opening a review, correcting it or dismissing it retains the existing version/approval controls. Creating an intentional test clears the search and returns to Pending review so the new item is visible.

The filter, search and page-size controls reset navigation. Status totals include all statuses matching the search within the current browsing boundary; the active status filter determines the result list. Counts and status transitions are live, so they can change as other reviewers resolve records. They are not industrial availability or failure-risk statistics.

## API additions

GET /api/sensor-quarantine keeps sensor_id, status=pending|replayed|dismissed|all and limit=1..100 (default 50). Optional q is at most 100 characters and is trimmed. Matching is case-insensitive under the database's normal lower/LIKE behavior, over the review UUID, original/corrected JSON text, validation reasons, review reason and corrected-event ID. JSON field names may also match. Percent/underscore are treated as literal search characters, not SQL wildcards. Queries are parameterized; no raw search text is executed as SQL. Matching is a bounded substring search, not a relevance-ranked or indexed full-text engine.

Response additions: summary (pending/replayed/dismissed counts), total_matching, page_cursor, next_cursor, snapshot_at, cursor_expires_at, normalized query and ordering. Existing items, supported_units and limit fields remain compatible. total_matching counts all rows for the active status/search within the current boundary, not only the returned page.

Pass next_cursor unchanged with the same sensor, status, q and limit to fetch the next page. page_cursor can refetch the current page, including the original first page for Previous navigation. Rows sort by created descending and UUID descending, with keyset positions covering equal-time ties. New records after snapshot_at are excluded until refresh; no offset skipping is used.

Navigation tokens are HMAC-signed, account/sensor/filter/page-size bound and expire after 15 minutes. Current authentication and canonical site access are checked before using a token. Invalid, tampered, expired or mismatched tokens return 422 with a message to refresh. Tokens contain navigation metadata, not original payloads, and are not authorization credentials.

## Runtime and consistency limits

The signing key is ephemeral per server process, appropriate to the current single-process local runtime. Restarting the server invalidates open navigation sessions; Refresh queue obtains new tokens. A multiworker/load-balanced deployment needs a shared managed signing-key strategy or a different cursor service before adoption. No persistent secret or .env changes were introduced.

The creation-time boundary does not freeze review status across requests. Status changes remain visible and resolved items can leave a Pending view. Read queries are read-only; correction/dismissal endpoints retain version checks and audit behavior. Existing intake, replay and snapshot APIs retain their prior semantics.

## Verification and acceptance

136 tests passed on SQLite and the same 136 on isolated PostgreSQL 18.6 with non-superuser runtime privileges. New cases traverse 63 equal-timestamp rows without missing/repeating IDs, preserve first-page navigation, exclude new submissions until refresh, verify account/site/filter binding and expiry/tampering rejection, check literal search and status counts, and exercise live status changes and sensor isolation. Existing workflow, intake/replay, unit conversion, alignment, migration, rollback and security checks also pass.

TypeScript and Vite production build passed. Alembic schema checks and PostgreSQL logical dump/restore preserved the tested quarantine rows, events, readings and projections. The schema is unchanged at 0006. Browser interaction for this increment remains unverified because local browser access was disabled; follow the installed-app walkthrough above. One existing Starlette test-client deprecation warning remains.

Phase 3 is still partial. Retention/partitioning, broker/device identity, live PostgreSQL cutover, production indexing/capacity, streaming recovery and operational restore objectives remain further work. This update does not claim production-scale queue performance or industrial-model validation.
