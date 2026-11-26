# Local condition attention — 26 November 2026

The header notification bell now checks the permitted condition inbox when opened by an engineer or administrator. It shows the server's unreviewed total and up to four newest matches, including site, immutable revision, last processed signal state and historical trigger time in GST. Opening the panel does not acknowledge, assign or resolve anything. The inbox remains the place to review evidence and act.

The panel fetches on open and on explicit refresh. Its timestamp describes the completed check; it is not a push subscription, unread-message count or proof of current equipment condition. Closing/remounting the panel cancels acceptance of the older request result. Account, role or selected-site changes close the panel; scoped keys prevent reuse of another context's result. Loading and failed requests clear the previous result and show an explicit status, never a false zero. Restricted roles make no condition-inbox request and see an access explanation. Backend permissions remain authoritative.

Each match entry now opens its exact bookmarkable condition-review page. The link preserves the record identity and still requires the recipient's existing role and site access. See CONDITION_MATCH_LINKS.md for detail routing and access checks.

Existing demonstration episodes appear in their own section, with a separate count and monitoring link. They are not added to the rule-match total. The previous demonstration-only bell dot was removed because it did not represent the combined review queue. Acknowledged and resolved rule matches remain available through inbox filters. Site selection still applies when opening the inbox.

No outbound email, escalation, routing, read receipts, persistent notification records or scheduled delivery are implemented by this change. Those remain development work. No database migration, authentication change, physical action or review decision is performed. Database schema remains 0016.
