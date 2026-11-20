# Phase 3, Step 8: private original-document archive

New accepted PDF/TXT/MD uploads retain their exact original bytes together with extracted text. The originals are private database records, not public static files or filesystem paths. This increment adds permission-checked attachment download, archive labels and checksum verification in recovery checks. It remains a local reference implementation.

## Install and walkthrough

Prerequisite: Step 7 installed. Stop Sentinel with Ctrl+C, run Apply-Phase3Step8.ps1, restart scripts/run.py and refresh Ctrl+F5. The checked updater backs up SQLite and application files, then creates revision 0007. No dependency install or whole-project replacement is needed. Existing documents, passwords, readings, review decisions, reports and snapshot provenance are preserved.

1. Sign in as Engineer or Admin. Open Knowledge base and click Upload document.
2. Choose a text-based PDF, TXT or MD file. A small optional fixture, Sentinel_Original_Archive_Test.txt, is supplied beside the updater outputs.
3. Enter a descriptive title such as Original archive verification, choose the permitted site/applicability and submit.
4. The new library card shows Original archived. Open it and select Download original. Compare its contents with the uploaded file. Downloads are attachments; the app does not render original PDF content inline.
5. Open an older seeded document. It shows Extracted text only / Original file not retained. Its text citations and existing identity remain available.
6. Sign in as an all-site Admin and run Workspace settings > Backup & recovery verification > Run recovery check.
7. Expand the new report. Confirm original files verified is at least one, checksums/schema/table contents match and the number of documents without originals is explicitly shown. Older reports remain visible and do not retrospectively claim original-file coverage.

Do not re-use an old pre-archive upload idempotency key. Uploading a source again uses a new document identity; it does not overwrite or manufacture an original for an earlier record.

## Persistence and API

Revision 0007 creates document_originals with document_id as PK/FK, deferred binary content (BLOB on SQLite / bytea on PostgreSQL), SHA-256, byte size, MIME type and archive timestamp. Only newly accepted uploads create rows. No legacy bytes are reconstructed from extracted text. Document metadata, extracted pages, original bytes, audit and idempotency receipt commit in one database transaction; failure rolls them back together, avoiding orphan files.

The existing upload endpoint and multipart fields remain the entry point. Accepted formats and limits remain a text-based PDF or UTF-8 TXT/MD, at most 10 MiB per file. Scanned/encrypted/unsupported or unusable documents are still rejected. Client MIME declarations are ignored in favor of the accepted parser/extension. Display filenames are stripped of path components/control characters and limited to 240 characters. Upload idempotency now binds the sanitized filename and archive behavior in addition to checksum/site/title/applicability. Same-key retries do not duplicate originals; changed filenames/content return conflict.

GET /api/documents and GET /api/documents/{id} add original_available, original_status, original_bytes, original_media_type and original_archived_at. List/detail metadata does not load deferred binary content. Existing fields and extracted-text retrieval stay available.

GET /api/documents/{id}/original checks the current authenticated user's canonical site permissions through the document. Allowed read-only roles may download originals at their permitted sites; Engineer/Admin are still required to upload. Missing/unavailable records return 404. Before returning bytes, the endpoint checks actual length and SHA-256 against both archive and document metadata; a mismatch returns 409 without serving the content. It returns an attachment with an encoded filename, no-store, nosniff and sandbox headers. No public file URL, anonymous download, original-edit/delete or archive backfill endpoint is added.

## Recovery extension

Original bytes are part of the SQLite snapshot, so no separate database/filesystem capture window is needed. The updated recovery check validates each archived file's size/checksum/document association before accepting the backup and again after isolated restoration. It reports original_files_verified, original_file_bytes and documents_without_original. Every table, including document_originals, remains subject to database checksum, schema, integrity, FK and content comparisons.

Manifest format 1 remains supported; older manifests without the optional originals summary still require database integrity/content checks. Older saved reports are labelled as not having measured original-file coverage. Existing backups are not rewritten. A failed original-file check causes the recovery run to fail; source data is never replaced.

The recovery action remains SQLite-only, limited to a 256 MiB database including archived bytes. PostgreSQL storage/download is implemented and tested, while its operational backup procedure remains separate. Large original files grow the database; object storage, encryption/retention policy, malware scanning/parser isolation and production capacity validation remain further work. A retained original is not a claim that its content or equipment applicability has been approved.

## Verification and limits

163 backend tests passed on SQLite and 163 on isolated PostgreSQL 18.6 using a non-superuser runtime role. New checks cover real text-based PDF plus TXT/MD byte-for-byte retention/download, deferred metadata, site/session/role checks, idempotency/filename binding, safe attachment names, unavailable legacy originals, transactional rollback, archive constraints, tampered-content refusal, recovery checksum validation, old manifest compatibility and revision 0006-to-0007 preservation.

Fresh/legacy migration and metadata checks passed. PostgreSQL logical dump/restore preserved actual tested binary-original rows as well as earlier records and provenance. TypeScript/Vite build passed. Browser interaction for this increment remains unverified because local browser access was disabled; complete the installed-app walkthrough above. One existing Starlette test-client deprecation warning remains.

Phase 3 remains partial. Operational archive policy, retention/partitioning, off-device backups, industrial device/broker ingestion, live PostgreSQL cutover, production scalability and full recovery objectives still need work. This release does not add OCR, semantic model embeddings, a production LLM or real vendor integration.
