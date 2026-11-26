import type { Page } from "../types";
export type ProductModule = {
  id: string;
  name: string;
  group: string;
  purpose: string;
  roles: string;
  route?: Page;
  current: string;
  availability?: string;
  functions: string[];
  screens: string[];
  gate: string;
};
export const moduleGroups = [
  "All modules",
  "Foundation",
  "Equipment & data",
  "Intelligence",
  "Maintenance",
  "Operations",
];
export const productModules: ProductModule[] = [
  {
    id: "sites",
    availability: "Single-company hierarchy available",
    name: "Organization & sites",
    group: "Foundation",
    purpose: "Give every asset a clear place in the operating hierarchy.",
    roles: "Admin",
    route: "organization",
    current:
      "Single-company profile, site creation, area/system hierarchy and versioned equipment assignment are available. Production identity and hosting work remain.",
    functions: [
      "Organization profile and operating time zones",
      "Site → area → system → equipment hierarchy",
      "Operating calendars and site onboarding",
      "Permission-controlled bulk imports",
    ],
    screens: [
      "Organization profile",
      "Site directory",
      "Hierarchy navigator",
      "Import review",
    ],
    gate: "Verify site isolation and identity mapping using representative customer data.",
  },
  {
    id: "access",
    availability: "Local access and administrator MFA available",
    route: "team",
    name: "Users & access",
    group: "Foundation",
    purpose: "Give each person the access and responsibilities they need.",
    roles: "Admin",
    current: "Team and site access, disable/reactivate, session revocation, invitations, password recovery and administrator authenticator MFA are implemented. Enterprise identity and production deployment acceptance remain.",
    functions: [
      "User invitations and recovery",
      "Enterprise sign-in and MFA",
      "Role and site permission matrix",
      "Session control and separation of approval duties",
    ],
    screens: [
      "User directory",
      "Role matrix",
      "Invitation flow",
      "Active sessions",
    ],
    gate: "Test server-side permission boundaries, recovery and approval-duty separation.",
  },
  {
    id: "assets",
    name: "Equipment registry",
    group: "Equipment & data",
    purpose:
      "One workspace for equipment identity, context and service history.",
    roles: "Admin · Engineer · Planner",
    route: "assets",
    current:
      "Registry, specifications, equipment details and permitted-site views are available.",
    functions: [
      "Lifecycle and service history",
      "Criticality and manufacturer metadata",
      "Customer asset photos and linked documents",
      "Bulk import with duplicate and mapping review",
    ],
    screens: [
      "Equipment registry",
      "Equipment workspace",
      "Import preview",
      "Lifecycle history",
    ],
    gate: "Reconcile asset identities with the customer equipment register.",
  },
  {
    id: "sensors",
    name: "Sensors & calibration",
    group: "Equipment & data",
    purpose: "Make each measurement traceable and understandable.",
    roles: "Admin · Engineer",
    route: "sensors",
    current:
      "Sensor identity, canonical units, events and freshness settings are available.",
    functions: [
      "Calibration records and due dates",
      "Measurement ranges and sampling frequency",
      "Channel-to-equipment mapping",
      "Quality, unit conversion and freshness rules",
    ],
    screens: [
      "Sensor registry",
      "Channel details",
      "Calibration history",
      "Mapping review",
    ],
    gate: "Validate units, channel mappings and calibration process against site requirements.",
  },
  {
    id: "connections",
    name: "Connections & gateways",
    group: "Equipment & data",
    purpose:
      "Bring readings into Sentinel through managed, observable connections.",
    roles: "Admin · Engineer",
    route: "settings",
    current:
      "Asset-scoped HTTP gateways exist. Plant connectors and offline buffering are planned.",
    functions: [
      "Required MQTT, OPC UA or historian connector",
      "Gateway provisioning and credential lifecycle",
      "Offline buffering and reconnection",
      "Connection diagnostics and certificate monitoring",
    ],
    screens: [
      "Connection catalog",
      "Gateway setup",
      "Connection health",
      "Delivery diagnostics",
    ],
    gate: "Trace actual plant measurements from source to screen under connection failure and recovery.",
  },
  {
    id: "quality",
    name: "Data quality & history",
    group: "Equipment & data",
    purpose: "Keep unreliable data out of operational decisions.",
    roles: "Engineer · Admin",
    route: "sensors",
    current:
      "Event validation, quarantine, controlled replay and reviewed alignment exist.",
    functions: [
      "Late and out-of-order event policies",
      "Timestamp and duplicate diagnostics",
      "Retention and historical exploration",
      "Controlled corrections with provenance",
    ],
    screens: [
      "Quality dashboard",
      "Rejected-data queue",
      "Historical explorer",
      "Replay review",
    ],
    gate: "Verify data integrity, repeat submissions, clock errors and retention at expected volume.",
  },
  {
    id: "monitoring",
    name: "Live monitoring",
    group: "Equipment & data",
    purpose: "Follow equipment condition with freshness and operating context.",
    roles: "Engineer · Planner · Technician",
    route: "monitor",
    current: "Four-channel monitoring and simulated replay are available.",
    functions: [
      "Saved views and flexible time ranges",
      "Multi-channel and equipment comparison",
      "Operating-state context",
      "Explicit missing, stale and disconnected states",
    ],
    screens: [
      "Live signals",
      "Trend comparison",
      "Saved views",
      "Equipment status",
    ],
    gate: "Validate live-source freshness, trend accuracy and behavior during outages.",
  },
  {
    id: "alerts",
    availability: "Local rule and review workflow available",
    name: "Conditions & alerts",
    group: "Intelligence",
    purpose: "Turn sustained conditions into accountable review tasks.",
    roles: "Admin · Engineer",
    route: "conditions",
    current: "Configurable rule previews, saved revisions, controlled activation, persistence/hysteresis, match reviews, ownership and evidence are implemented. Operational alert delivery, escalation and suppression remain.",
    functions: [
      "Thresholds, hysteresis and persistence",
      "Deduplication and severity routing",
      "Escalation and maintenance suppression",
      "Acknowledgement and resolution evidence",
    ],
    screens: [
      "Alert inbox",
      "Rule editor",
      "Episode timeline",
      "Suppression review",
    ],
    gate: "Test false alarms, repeat episodes, escalation and suppression with engineers.",
  },
  {
    id: "investigations",
    availability: "Linked evidence workflow available",
    name: "Investigations",
    group: "Intelligence",
    purpose:
      "Connect observations to evidence and an engineer-reviewed recommendation.",
    roles: "Engineer · Approver",
    route: "intelligence",
    current: "Local investigations preserve matched rule/trigger evidence and a separate fresh analysis snapshot. Independent approval and versioned recommendations are available; real-case engineering validation remains.",
    functions: [
      "Findings, comments and version history",
      "Linked readings and document evidence",
      "Recommendation changes and review routing",
      "Model/version details and uncertainty",
    ],
    screens: [
      "Investigation workspace",
      "Evidence viewer",
      "Findings history",
      "Recommendation review",
    ],
    gate: "Validate evidence traceability and recommendation quality on real operating cases.",
  },
  {
    id: "knowledge",
    name: "Knowledge & documents",
    group: "Intelligence",
    purpose:
      "Keep relevant maintenance knowledge available with source context.",
    roles: "Engineer · Admin",
    route: "knowledge",
    current:
      "Search, page evidence and private original-file retention are available.",
    functions: [
      "Document versions and retirement",
      "Upload validation and access control",
      "OCR where scanned documents require it",
      "Search relevance and citation review",
    ],
    screens: [
      "Document library",
      "Source viewer",
      "Upload review",
      "Version comparison",
    ],
    gate: "Verify permissions, upload protections, extraction quality and source citations.",
  },
  {
    id: "approvals",
    name: "Approvals",
    group: "Maintenance",
    purpose: "Make decisions explicit before work moves forward.",
    roles: "Approver · Engineer · Planner",
    route: "intelligence",
    current:
      "Recommendation approval and rejection workflows exist in the reference app.",
    functions: [
      "Configurable routing and delegation",
      "Decision reasons and revision requests",
      "Overdue review and escalations",
      "Invalidate approvals when material evidence changes",
    ],
    screens: [
      "Approval inbox",
      "Evidence comparison",
      "Decision history",
      "Delegation setup",
    ],
    gate: "Verify approval scope, duty separation and evidence-change invalidation.",
  },
  {
    id: "planning",
    availability: "Basic local planning available",
    route: "orders",
    name: "Maintenance planning",
    group: "Maintenance",
    purpose: "Turn approved needs into realistic, scheduled work.",
    roles: "Planner · Engineer",
    current: "Approved recommendations can become planned work orders with an assignee and due date. Preventive schedules, resource/parts planning and downtime windows remain.",
    functions: [
      "Preventive and condition-based schedules",
      "Reusable job plans and skill requirements",
      "Parts and downtime-window planning",
      "Priority and backlog management",
    ],
    screens: [
      "Planning board",
      "Maintenance calendar",
      "Job-plan editor",
      "Resource planning",
    ],
    gate: "Review a complete schedule with planners, equipment availability and job constraints.",
  },
  {
    id: "execution",
    name: "Work execution",
    group: "Maintenance",
    purpose: "Guide technicians and capture what actually happened.",
    roles: "Technician · Planner · Approver",
    route: "orders",
    current:
      "Reference work-order states and completion exist. Mobile field execution needs expansion.",
    functions: [
      "Assignments and technician checklists",
      "Photos, measurements and notes",
      "Labor and parts usage",
      "Completion review and return-to-service verification",
    ],
    screens: [
      "Work-order workspace",
      "Technician tasks",
      "Inspection form",
      "Completion review",
    ],
    gate: "Complete one real maintenance job with evidence and independently verified return to service.",
  },
  {
    id: "reliability",
    name: "Outcomes & reliability",
    group: "Intelligence",
    purpose:
      "Learn from maintenance and measure changes in equipment performance.",
    roles: "Engineer · Planner",
    route: "reliability",
    current:
      "The reliability lab is available with synthetic reference analytics.",
    functions: [
      "Failure codes and downtime records",
      "Repeat-failure and maintenance-effectiveness analysis",
      "MTBF and MTTR with agreed definitions",
      "Predictive models only after real-data validation",
    ],
    screens: [
      "Reliability dashboard",
      "Failure analysis",
      "Outcome review",
      "Model evaluation",
    ],
    gate: "Reconcile calculations with operating records and validate any predictive claims separately.",
  },
  {
    id: "notifications",
    availability: "Account email available · alert delivery planned",
    route: "team",
    name: "Notifications",
    group: "Operations",
    purpose:
      "Deliver the right message and show whether it reached its destination.",
    roles: "Admin · All assigned users",
    current: "Account invitation/recovery email and delivery status are implemented for configured local use. The header attention panel checks unreviewed rule matches inside the portal. External condition-alert delivery, notification preferences, routing and escalation remain planned.",
    functions: [
      "Approved email or messaging delivery",
      "User preferences and routing",
      "Delivery tracking and safe retries",
      "Escalation with acknowledgement links",
    ],
    screens: [
      "Notification preferences",
      "Routing rules",
      "Delivery log",
      "Escalation setup",
    ],
    gate: "Prove delivery, retry behavior and permission-safe acknowledgement links.",
  },
  {
    id: "integrations",
    availability: "Local CMMS simulator available",
    route: "orders",
    name: "Integration management",
    group: "Operations",
    purpose: "Keep Sentinel and external maintenance systems consistent.",
    roles: "Admin · Planner",
    current:
      "The application has a local CMMS simulator; no vendor CMMS is connected.",
    functions: [
      "CMMS work-order synchronization",
      "External equipment identity mapping",
      "Webhooks, retries and reconciliation",
      "Conflict handling and failed-sync review",
    ],
    screens: [
      "Integration setup",
      "Mapping editor",
      "Sync history",
      "Failed-sync queue",
    ],
    gate: "Verify synchronization, duplicate prevention and conflict recovery with the chosen CMMS.",
  },
  {
    id: "reports",
    availability: "Local exports available",
    route: "assets",
    name: "Reporting",
    group: "Operations",
    purpose:
      "Give each audience an accurate view of operations and maintenance.",
    roles: "Engineer · Planner · Admin",
    current: "Permission-scoped asset exports and reliability briefs are available. A report library, agreed outcome calculations and scheduled delivery remain.",
    functions: [
      "Operations summaries and equipment history",
      "Backlog and alert-response reporting",
      "Permission-controlled exports",
      "Scheduled reports and delivery status",
    ],
    screens: [
      "Report library",
      "Report filters",
      "Schedule setup",
      "Export history",
    ],
    gate: "Check report calculations, site permissions and exported data against source records.",
  },
  {
    id: "administration",
    availability: "Local audit and recovery checks available",
    name: "Audit & administration",
    group: "Foundation",
    purpose: "Keep changes traceable and services recoverable.",
    roles: "Admin",
    route: "activity",
    current:
      "Audit history, local status and isolated SQLite recovery checks exist.",
    functions: [
      "Protected audit and configuration history",
      "Service health and operational monitoring",
      "Automated backups and restore records",
      "Retention, incident handling and access reviews",
    ],
    screens: [
      "Audit explorer",
      "System health",
      "Backup & recovery",
      "Configuration history",
    ],
    gate: "Demonstrate security checks, off-machine recovery and operational support readiness.",
  },
];
export { developmentPhases } from "./developmentStatus";
export const deploymentOptions = [
  [
    "Customer isolation",
    "If serving multiple customers",
    "Tenant-specific data, permissions, storage and isolation tests.",
  ],
  [
    "Offline technician work",
    "If field connectivity is unreliable",
    "Offline task capture, synchronization and conflict review.",
  ],
  [
    "Inventory & procurement",
    "If Sentinel owns purchasing",
    "Parts stock, reservations and purchasing; otherwise integrate ERP/CMMS.",
  ],
  [
    "Permit & isolation records",
    "If required by site procedures",
    "Links to approved permit-to-work and isolation processes.",
  ],
  [
    "Arabic & localization",
    "If required by users",
    "Translated content, right-to-left layouts and local formats.",
  ],
  [
    "Advanced vibration analysis",
    "If waveform data is available",
    "Waveforms, spectra and engineering-reviewed diagnostics.",
  ],
  [
    "Predictive failure models",
    "After sufficient real data exists",
    "Validation, uncertainty, drift monitoring and human review.",
  ],
  [
    "Subscriptions & billing",
    "If commercially required",
    "Plans, usage limits and customer billing administration.",
  ],
];
