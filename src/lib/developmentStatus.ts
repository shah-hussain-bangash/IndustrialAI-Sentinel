import type { Page } from "../types";

export const developmentReviewedOn = "27 November 2026";
export const phaseStatusLabels = { local: "Local workflow available", partial: "Partly implemented", planned: "Planned" };
export type DevelopmentPhase = {
  id: string; name: string; status: keyof typeof phaseStatusLabels; scope: string;
  delivered: string[]; remaining: string[]; verification: string; gate: string; route?: Page;
};
export const developmentPhases: DevelopmentPhase[] = [
  {
    id: "definition", name: "Product definition", status: "partial",
    scope: "Agree the equipment, users, data sources, hosting and operating responsibilities.",
    delivered: ["A single-company, multi-site scope and the core equipment-to-maintenance journey are defined."],
    remaining: ["Confirm a named pilot owner, first real data source and deployment environment.", "Agree expected volume, recovery targets and measurable acceptance cases."],
    verification: "Local reference workflows provide a basis for scope review.",
    gate: "Approved pilot scope, owners and measurable acceptance criteria.",
  },
  {
    id: "experience", name: "UI & workflow design", status: "local", route: "overview",
    scope: "Provide clear navigation, evidence views and recoverable user journeys.",
    delivered: ["Workspace navigation, photographic page headers, role-aware forms and evidence views are available.", "Thirteen tools load on demand, with loading messages and recovery after a failed load."],
    remaining: ["Complete representative mobile and accessibility acceptance across every operating journey."],
    verification: "Desktop workflows and isolated loading/recovery checks have been exercised.",
    gate: "User acceptance of desktop, mobile, error and disconnected journeys.",
  },
  {
    id: "foundation", name: "Platform foundation", status: "local", route: "organization",
    scope: "Maintain company identity, site access, accounts and controlled upgrades.",
    delivered: ["Company/site hierarchy, equipment placement, team roles, disable/reactivate and session revocation are available.", "Invitation/recovery email, personal passwords, administrator authenticator MFA and checked SQLite upgrades are implemented."],
    remaining: ["Prepare staging/production hosting, HTTPS, storage sizing and retention.", "Agree enterprise identity requirements and operational ownership."],
    verification: "Role/site boundaries, stale edits, upgrade preservation and rollback have local test evidence.",
    gate: "Accepted identity controls and a repeatable deployment in the selected environment.",
  },
  {
    id: "connections", name: "Real data connection", status: "partial", route: "settings",
    scope: "Bring representative equipment readings into the workspace reliably.",
    delivered: ["Equipment-scoped HTTP gateways, a synthetic test sender, canonical units, quality checks, quarantine and snapshot alignment are available."],
    remaining: ["Connect the first approved plant, historian or gateway source and validate its identity mapping.", "Prove delivery during outages, buffering/reconnection and representative sampling conditions."],
    verification: "Synthetic ingestion and permission/data-quality checks are covered locally.",
    gate: "Trace real readings from source to screen through loss and recovery.",
  },
  {
    id: "conditions", name: "Condition management", status: "local", route: "conditions",
    scope: "Turn sustained signals into traceable review and investigation work.",
    delivered: ["Rule previews, immutable saved revisions, controlled activation, persistence, hysteresis and quality/gap handling are implemented.", "Match reviews, ownership history, trigger evidence, linked investigations and investigation-status filters are available.", "The header attention panel checks unreviewed rule matches and opens exact, bookmarkable match-review records within permitted site access.", "Permission-scoped JSON and printable condition-review downloads include saved evidence and explicitly bounded review/ownership history."],
    remaining: ["Implement approved alert-delivery routing, retries, escalation and maintenance suppression.", "Validate thresholds and detection-to-review behavior with engineers using real operating cases."],
    verification: "Synthetic trigger, paused match, review history and linked-draft flows have been exercised.",
    gate: "Accepted condition behavior, review ownership and notification/suppression cases.",
  },
  {
    id: "maintenance", name: "Maintenance execution", status: "partial", route: "orders",
    scope: "Move reviewed recommendations into planned work and recorded outcomes.",
    delivered: ["Version-bound independent approval, approval invalidation, basic work-order planning and local execution states are available.", "A persistent local CMMS simulator supports submission and reconciliation tests."],
    remaining: ["Expand job plans, resources, parts, field evidence and return-to-service verification.", "Connect and rehearse the selected vendor CMMS workflow."],
    verification: "Local approval-duty separation and work-order state checks are covered by automated tests.",
    gate: "A controlled maintenance job with traceable findings and independently accepted recovery evidence.",
  },
  {
    id: "reliability", name: "Reliability & reporting", status: "partial", route: "reliability",
    scope: "Review priorities and reconcile maintenance outcomes with source records.",
    delivered: ["Local triage, trend comparison, what-if scenarios and permission-scoped exports are available."],
    remaining: ["Agree failure/downtime codes and MTBF/MTTR definitions, then reconcile calculations with real records.", "Develop the report library and any approved scheduled delivery."],
    verification: "Current scoring and analytics use a synthetic reference baseline.",
    gate: "Engineering acceptance of calculations, outcomes and any predictive claims.",
  },
  {
    id: "hardening", name: "Production hardening", status: "partial", route: "settings",
    scope: "Establish operational security, recoverability, monitoring and capacity.",
    delivered: ["Local authentication/MFA, site checks, audit records, idempotent commands and backed-up updates are implemented.", "An isolated SQLite recovery check and lighter page loading have local verification evidence."],
    remaining: ["Establish off-machine backups, restore targets, service monitoring, durable workers and retention.", "Complete representative load/security review and staging/production release rehearsals."],
    verification: "Local checks cover parts of these controls; production acceptance remains open.",
    gate: "Documented launch checks with environment-specific evidence and named support owners.",
  },
  {
    id: "pilot", name: "Controlled pilot", status: "planned",
    scope: "Train users and operate within a limited, agreed real-site boundary.",
    delivered: [],
    remaining: ["Name the pilot owner and users, complete prerequisite gates and prepare training/runbooks.", "Collect real-site acceptance results, incidents and support feedback."],
    verification: "Real-site pilot acceptance is pending.",
    gate: "Recorded user acceptance and operational sign-off for the pilot scope.",
  },
  {
    id: "rollout", name: "Production rollout", status: "planned",
    scope: "Expand only after the controlled pilot and launch gates are accepted.",
    delivered: [],
    remaining: ["Agree rollout stages, release/rollback procedures and incident ownership.", "Establish ongoing monitoring, support and periodic access/recovery reviews."],
    verification: "Production rollout acceptance is pending.",
    gate: "Accepted operational ownership, launch evidence and ongoing monitoring.",
  },
];
