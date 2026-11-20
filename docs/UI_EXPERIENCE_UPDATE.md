# Sentinel interface experience update

This local interface increment keeps the current navy/blue identity and all existing API permissions and publication rules. It changes frontend files, UI tests and CI invocation only. Schema and backend code remain at revision 0008.

## Changes

- Larger text, stronger contrast, consistent cards, buttons, tables and keyboard focus states across the portal.
- Refined sign-in panel with clear role descriptions and direct role cards.
- Overview shortcuts for sensor review, investigations and work orders using current data.
- Browser hash navigation retains the current page on refresh and supports back/forward.
- Workspace settings has six visible sections instead of one long page: Workspace, Telemetry access, Site directory, Backup & recovery, Account & password and System status.
- Newly issued gateway credentials have a Send test sample button. It sends one four-channel simulated batch with the gateway bearer credential, credentials omitted, no browser account session and no clipboard step. Raw keys remain only in UI memory. Rotation and clearing behavior remains explicit. This in-browser exercise is not a test of external transport, MQTT or physical devices.
- Failed sample requests keep the request key and exact body for safe retry. A confirmed batch disables further submission from that issued-key panel to reduce duplicates. A new credential issuance starts a new test.
- Snapshot review shows a freshness countdown derived from canonical sensor limits, four readable values and a deliberate review checkbox. The publication action stays available while scrolling. Expired readings disable it. Server validation still decides whether a publication is accepted; the browser countdown is an estimate based on the local clock.
- After a rejected publication, the old ready preview is discarded and fetched again. After success, the success state explains that a new frame is required, rather than presenting a contradictory duplicate-publication warning.
- Evidence IDs remain available through expandable traceability sections. Audit adds category filters, search through evidence details and expandable record IDs.
- Responsive layout and reduced-motion behavior are included.

## Apply

Run Apply-ExperienceUpdate.ps1 -ProjectPath "C:\industrialai-sentinel". It checks source baselines and all payload hashes before copying. Existing local edits in touched source files stop the update for review. It backs up the previous interface under .theme-backups and installs dist/index.html last, keeping older hashed assets in place for open tabs. No database migration, dependency installation, backend restart, automatic commit or push is performed. If Sentinel is already running, refresh with Ctrl+F5 after installation.

## Walkthrough

1. Sign in. Inspect the overview, shortcuts and more readable tables.
2. Open Workspace settings > Telemetry access. Create a gateway for a test asset or rotate an existing test gateway (this invalidates its previous sender key).
3. With the one-time credential visible, click Send test sample. Confirm four accepted events. External sender/clipboard use remains an alternative.
4. Open Sensor registry > Inspect events > Equipment alignment for the same asset. Keep simulation paused. Review values and the countdown, check I reviewed all four readings, then publish while eligible.
5. After success, inspect Live monitoring and Activity & audit. Evidence IDs are expandable.

The local build and automated checks are recorded in docs/evidence/ui-experience-verification.json. The development browser walkthrough uses isolated synthetic data, not the running user's database. No industrial readiness or predictive-accuracy claim is added.
