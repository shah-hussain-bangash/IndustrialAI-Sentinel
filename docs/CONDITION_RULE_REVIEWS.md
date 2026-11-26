# Condition management, increment 4: acknowledgement and review resolution

Load a saved draft in Workspace settings > Condition rules. Its recent rule-match table now shows both signal state and review state. **Review match** opens its review notes and history. Engineers and administrators with current access to that equipment can acknowledge an unreviewed match. They can resolve an acknowledged review only after the signal has ended: cleared, interrupted by invalid data or a gap, paused, or replaced. An active signal cannot be manually marked resolved through this review workflow.

Review status is separate from signal state, activation and maintenance. Acknowledgement does not silence the evaluator or close the match. Resolution records a completed review of an ended match; it does not assert that a physical fault was found or repaired and does not complete a work order. A paused or interrupted match may need further investigation even if its administrative review is resolved. Record the actual assessment and evidence limits in the review note.

Each transition requires a note of 5–1000 characters. Review history retains author identity/name at action time, timestamp, state, version and note. Previous review entries have no edit/delete route. The current workflow is unreviewed → acknowledged → resolved; reopening or adding general comments is not implemented. Triggered/cleared signal data and original draft revision history are retained separately.

## API and concurrency

GET /api/condition-rules/matches/{id}/reviews returns current review and signal state plus bounded history. POST /{id}/review accepts action (acknowledge or resolve), expected_version (0 initially) and reason. Existing role, canonical site membership, session/MFA, CSRF/origin checks and idempotency keys apply. A no-op write locks the match row before checking the latest review version and signal state, serializing concurrent reviews and signal closure. Outdated edits are rejected. Retrying a completed request with the same key/payload returns the existing receipt. On uncertain delivery, reload the review before submitting another action.

Every transition creates an activity audit record. Review records are application append-only; direct database administration remains outside that guarantee. No email, maintenance dispatch, plant control, diagnosis or automatic physical-work completion is performed.

## Upgrade and verification

Migration 0014 adds condition_rule_reviews, linked to an existing match. Existing matches, activation/paused state, drafts/revisions, readings, accounts and enrolled MFA are unchanged. Existing matches start with a derived unreviewed state (no review row); installation does not acknowledge or resolve anything. The installer checks stopped-server/schema/source prerequisites, backs up database and application files, supports rollback, and resumes the existing safe source-sync helper.

The local reference limitations of CONDITION_RULE_ACTIVATION.md remain. Review acceptance on the installed portal is a separate step after installation. Automated tests cover acknowledgement/resolution, active-match restrictions, idempotency, stale updates, history/audit retention, role/CSRF/validation controls and unchanged signal, activation and work-order data.
