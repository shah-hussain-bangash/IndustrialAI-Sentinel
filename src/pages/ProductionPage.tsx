import { useState, useEffect, useRef } from "react";
import {
  Search,
  Layers,
  ShieldCheck,
  ChevronRight,
  CheckCircle2,
  ClipboardList,
  X,
  LockKeyhole,
} from "lucide-react";
import type { Data, Page } from "../types";
import {
  productModules,
  moduleGroups,
  developmentPhases,
  deploymentOptions,
} from "../lib/productionPlan";
import { Button } from "../components/ui";
export function ProductionPage({
  data,
  navigate,
}: {
  data: Data;
  navigate: (page: Page) => void;
}) {
  const detailRef = useRef<HTMLElement>(null);
  const [tab, setTab] = useState("Modules");
  const [group, setGroup] = useState("All modules");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    if (selected && tab === "Modules")
      detailRef.current?.scrollIntoView({ block: "start" });
  }, [selected, tab]);
  const module = productModules.find((m) => m.id === selected);
  const filtered = productModules.filter(
    (m) =>
      (group === "All modules" || m.group === group) &&
      `${m.name} ${m.purpose} ${m.functions.join(" ")}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const current = [
    ["Equipment", data.assets.length],
    ["Sensor channels", data.overview.stats.sensors],
    ["Open work orders", data.overview.stats.open_orders],
    ["Pending reviews", data.overview.stats.pending_reviews],
  ];
  return (
    <div className="production-workspace">
      <section className="production-hero">
        <div>
          <span className="production-eyebrow">
            PRODUCT DESIGN / IMPLEMENTATION PLAN
          </span>
          <h2>One connected operating journey.</h2>
          <p>
            Prepare the complete platform around the workflows your team needs.
          </p>
          <div className="production-status">
            <Layers size={17} />
            <strong>UI preparation</strong>
            <span>Production readiness has not been assessed.</span>
          </div>
        </div>
        <div className="production-hero-summary">
          <strong>{productModules.length}</strong>
          <span>product modules</span>
          <small>
            Existing reference workflows and planned capabilities are identified
            separately.
          </small>
        </div>
      </section>
      <div className="production-notice">
        <ShieldCheck size={21} />
        <p>
          <strong>Design workspace.</strong> New module specifications, roadmap
          and launch criteria are available for review. They do not connect
          equipment, configure external services or establish production
          readiness.
        </p>
      </div>
      <section
        className="production-current"
        aria-label="Current workspace records"
      >
        {current.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>Current permitted workspace</small>
          </div>
        ))}
      </section>
      <nav className="production-tabs" aria-label="Product planning views">
        {[
          "Modules",
          "End-to-end journey",
          "Development phases",
          "Launch requirements",
          "Deployment options",
        ].map((name) => (
          <button
            key={name}
            aria-current={tab === name ? "page" : undefined}
            className={tab === name ? "active" : ""}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </nav>
      {tab === "Modules" && (
        <>
          <div className="production-section-title">
            <div>
              <h2>Platform modules</h2>
              <p>
                Review each module's purpose, screens, responsibilities and
                release criteria.
              </p>
            </div>
            <label className="production-search">
              <Search size={18} />
              <input
                aria-label="Search product modules"
                placeholder="Find a module or capability"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>
          <div className="production-filters" aria-label="Module categories">
            {moduleGroups.map((name) => (
              <button
                key={name}
                className={group === name ? "active" : ""}
                aria-pressed={group === name}
                onClick={() => setGroup(name)}
              >
                {name}
              </button>
            ))}
          </div>
          {module && (
            <section
              ref={detailRef}
              className="production-detail"
              aria-label={`${module.name} design specification`}
            >
              <div className="production-detail-heading">
                <div>
                  <span className="production-eyebrow">{module.group}</span>
                  <h2>{module.name}</h2>
                  <p>{module.purpose}</p>
                </div>
                <button
                  className="icon-btn"
                  aria-label="Close module specification"
                  onClick={() => setSelected(null)}
                >
                  <X size={22} />
                </button>
              </div>
              <div className="production-existing">
                <strong>Current reference application</strong>
                <p>{module.current}</p>
                {module.route && (
                  <Button onClick={() => navigate(module.route!)}>
                    Open existing workspace
                  </Button>
                )}
              </div>
              <div className="production-detail-columns">
                <div>
                  <h3>Development scope</h3>
                  <ul>
                    {module.functions.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3>Screens to prepare</h3>
                  <ul>
                    {module.screens.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="production-detail-footer">
                <div>
                  <strong>Primary users</strong>
                  <p>{module.roles}</p>
                </div>
                <div>
                  <strong>Release evidence required</strong>
                  <p>{module.gate}</p>
                </div>
              </div>
            </section>
          )}
          <div className="production-module-grid">
            {filtered.map((m) => (
              <button
                key={m.id}
                className={`production-module ${selected === m.id ? "selected" : ""}`}
                onClick={() => setSelected(m.id)}
                aria-pressed={selected === m.id}
              >
                <span className="production-module-top">
                  <span>{m.group}</span>
                  <ClipboardList size={21} />
                </span>
                <h3>{m.name}</h3>
                <p>{m.purpose}</p>
                <span className="production-module-status">
                  {m.route
                    ? "Reference workflow + planned expansion"
                    : "Planned capability"}
                </span>
                <span className="production-module-bottom">
                  Review scope & screens
                  <ChevronRight size={18} />
                </span>
              </button>
            ))}
          </div>
          {!filtered.length && (
            <div className="production-empty">
              <h3>No matching modules</h3>
              <p>Try another term or choose All modules.</p>
            </div>
          )}
        </>
      )}
      {tab === "End-to-end journey" && (
        <section>
          <div className="production-section-title">
            <div>
              <h2>From signal to verified outcome</h2>
              <p>
                Each handoff needs a clear owner, evidence and an explicit next
                step.
              </p>
            </div>
          </div>
          <div className="production-journey">
            {[
              [
                "Connect equipment",
                "Admin / Engineer",
                "Choose source, map identities and prove authenticated delivery.",
                "connections",
              ],
              [
                "Validate readings",
                "Engineer",
                "Check units, timestamps, quality and data freshness.",
                "quality",
              ],
              [
                "Detect conditions",
                "Engineer",
                "Apply reviewed rules and create a traceable condition episode.",
                "alerts",
              ],
              [
                "Investigate evidence",
                "Engineer",
                "Review trends, operating context and source procedures.",
                "investigations",
              ],
              [
                "Approve maintenance",
                "Approver",
                "Record the decision, reasons and approved scope.",
                "approvals",
              ],
              [
                "Plan the work",
                "Planner",
                "Allocate skills, job plans, parts and downtime windows.",
                "planning",
              ],
              [
                "Execute safely",
                "Technician",
                "Follow approved site procedures and record findings.",
                "execution",
              ],
              [
                "Verify recovery",
                "Engineer / Approver",
                "Review post-work readings and return-to-service evidence.",
                "execution",
              ],
              [
                "Measure outcomes",
                "Engineer / Planner",
                "Record downtime, repair results and recurring failures.",
                "reliability",
              ],
            ].map(([title, owner, evidence, id], i) => (
              <article key={title}>
                <span className="production-step-index">{i + 1}</span>
                <div>
                  <h3>{title}</h3>
                  <strong>{owner}</strong>
                  <p>{evidence}</p>
                  <button
                    className="text-link"
                    onClick={() => {
                      setSelected(id);
                      setTab("Modules");
                    }}
                  >
                    Review module scope
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
      {tab === "Development phases" && (
        <section>
          <div className="production-section-title">
            <div>
              <h2>Development roadmap</h2>
              <p>
                Advance when acceptance evidence is available. No phase is
                marked production-complete.
              </p>
            </div>
          </div>
          <div className="production-phase-grid">
            {developmentPhases.map(([name, scope, gate], i) => (
              <article key={name}>
                <div>
                  <span>Phase {i + 1}</span>
                  <span className="production-phase-state">
                    {i === 1
                      ? "UI preparation"
                      : "Planned / verification required"}
                  </span>
                </div>
                <h3>{name}</h3>
                <p>{scope}</p>
                <footer>
                  <CheckCircle2 size={19} />
                  <span>
                    <strong>Completion requirement</strong>
                    {gate}
                  </span>
                </footer>
              </article>
            ))}
          </div>
        </section>
      )}
      {tab === "Launch requirements" && (
        <section>
          <div className="production-section-title">
            <div>
              <h2>Production launch requirements</h2>
              <p>
                These controls need implementation and evidence, beyond
                interface design.
              </p>
            </div>
          </div>
          <div className="production-launch-grid">
            {[
              [
                "Identity & security",
                "Enterprise identity, MFA, permissions, session management, secrets, upload protection and independent security review.",
              ],
              [
                "Deployment & release",
                "Development, staging and production environments; HTTPS; reviewed releases, migrations and rollback.",
              ],
              [
                "Storage & retention",
                "A database architecture sized for expected volume, secure document storage and enforceable retention.",
              ],
              [
                "Reliable processing",
                "Ingestion, integration and notification workers with safe retries, duplicate control and failure visibility.",
              ],
              [
                "Monitoring & support",
                "Service health, metrics, logs, alerting, incident response and named operational owners.",
              ],
              [
                "Backup & recovery",
                "Automated backups, appropriate off-machine copies, restore exercises and agreed recovery targets.",
              ],
              [
                "Industrial network boundaries",
                "Site-approved network segmentation, connector configuration and equipment-access boundaries.",
              ],
              [
                "Validation & pilot",
                "Representative data, performance testing, user acceptance, training and controlled site rollout.",
              ],
            ].map(([title, description]) => (
              <article key={title}>
                <LockKeyhole size={23} />
                <h3>{title}</h3>
                <p>{description}</p>
                <span>Evidence required</span>
              </article>
            ))}
          </div>
        </section>
      )}
      {tab === "Deployment options" && (
        <section>
          <div className="production-section-title">
            <div>
              <h2>Scope-dependent capabilities</h2>
              <p>
                Select these during product definition based on the customer and
                operating environment.
              </p>
            </div>
          </div>
          <div className="table-scroll panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Capability</th>
                  <th>When it applies</th>
                  <th>Scope to define</th>
                </tr>
              </thead>
              <tbody>
                {deploymentOptions.map(([name, when, scope]) => (
                  <tr key={name}>
                    <td>
                      <strong>{name}</strong>
                    </td>
                    <td>{when}</td>
                    <td>{scope}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
