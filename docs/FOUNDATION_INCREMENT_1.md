# Foundation increment 1: one company, multiple sites

## Implemented

- A persisted, single-company profile, initially named Your organization until an authorized administrator configures it.
- Administrator site creation. Only the creating administrator is granted membership; other accounts keep existing access. Refresh the browser after site creation to update the global site selector.
- Site areas and equipment systems with parent-scoped, normalized unique codes and versioned label updates.
- Equipment assignment and unassignment with independent placement versions. Equipment IDs, site IDs, legacy location labels, reading history, credentials and user passwords are preserved.
- Existing equipment starts unassigned. No hierarchy is inferred from old labels.
- SQL and application constraints reject cross-site placements and system parents. Rigid area/system types and immutable parents avoid cycles; moving parents or deleting hierarchy records is outside this increment.
- Company-wide profile and site creation require an administrator assigned to every site. Scoped administrators manage their permitted areas and systems. Engineers can assign permitted equipment. Other roles have read-only views.
- Mutations require authenticated role/site authorization, CSRF and idempotency keys; version checks reject stale changes. Audit evidence records changes.
- Organization & sites page retains the approved navy/gold photographic design. Its site selection follows the portal-wide site scope.

## Install

1. Stop the existing Sentinel server with Ctrl+C in its server terminal.
2. Run Apply-Foundation1.ps1 -ProjectPath C:\industrialai-sentinel from another PowerShell terminal.
3. Wait for FOUNDATION_INCREMENT_1=INSTALLED and FOUNDATION_UPGRADE=PASS; revision=0009.
4. Restart .venv\Scripts\python.exe scripts\run.py and refresh the browser.
5. Open #organization, save the actual company name, then create site areas and systems and assign equipment as needed.

The installer checks payload hashes and existing source before copying. It invokes the old database preflight before replacing code, so the application must be stopped. It backs up prior application files under .theme-backups/foundation-1-*. The checked upgrade creates a SQLite snapshot under the configured data/backups directory before migrating to revision 0009. Application files are restored if copying or the database upgrade fails; the checked upgrade restores its database snapshot on migration failure. No Git commit or push occurs.

The updater's -CheckOnly option checks source/payload compatibility only and does not change or migrate the database. Automatic installation supports the existing local SQLite deployment. PostgreSQL migration has not been validated for this increment and must be rehearsed separately before use.

## Verification

183 backend tests passed, including new organization/hierarchy permissions, repeat requests, version conflicts, invalid labels, duplicate codes, cross-site SQL constraints, creator-only new-site access, migration row preservation and repeated upgrade checks. One existing Starlette/httpx deprecation warning remains. TypeScript and production build passed.

The browser walkthrough uses isolated synthetic data: save a company profile, create an area and system, assign equipment, refresh to confirm persistence, create an empty site and inspect mobile layout. No actual customer company, hierarchy or site is preconfigured by the installer.

## Remaining production foundation work

User invitation and membership administration, account disable/recovery, enterprise sign-in/MFA, production storage/hosting, retention, operating calendars, external connectors, protected operational audit export and pilot readiness remain separate increments. A company profile is not multi-tenant isolation. This increment does not certify production readiness.
