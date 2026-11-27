# Printable condition-review report — 27 November 2026

Exact condition-match pages offer **Download printable report** alongside the JSON download. Both use the same authenticated, permission-scoped export endpoint. The printable file is a self-contained HTML document: open it in a browser and use Print to print or save as PDF. There is no automatic printer action or PDF-generation service.

The report includes identity/current review, matched rule settings and units, historical trigger details, recorded signals, review history, ownership history, linked-investigation summary and explicit scope limits. Zero values remain zero and unavailable values remain marked. Times display in Gulf Standard Time (UTC+4). History totals, included counts and omission warnings are retained; the output never implies omitted history was included. Approval summaries distinguish current approval from expired/invalidated approval, and malformed investigation links expose no identity. The report does not certify a physical fault, repair or maintenance completion.

All report-provided text is escaped before entering HTML. The document has no scripts, images, remote fonts, links, forms or tracking. A restrictive content-security policy blocks active/remote content. Screen/print styles include A4 margins, repeating table headers and row page-break guidance. Long notes may span pages according to the browser's print engine. The text and data remain selectable.

Before either download, the UI validates the format, match identity and history metadata; incomplete/inconsistent content produces an error. Existing role/site permissions apply when requesting the file. Downloaded copies remain outside subsequent portal access revocation and must be stored privately. This is a local readout, not a signed record, atomic database snapshot or backup.

This update is frontend-only. Schema remains 0016 and no account, MFA, rule state, review decision, ownership or investigation record is modified. Backend export behavior remains as documented in CONDITION_REVIEW_EXPORT.md.
