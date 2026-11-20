import { useState } from "react";
import {
  Box,
  Check,
  ChevronRight,
  Cpu,
  FileCheck2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  Workflow,
} from "lucide-react";
import { age, type User } from "../api";

import { Badge, Button, Empty } from "../components/ui";
import type { Data } from "../types";
export function IntelligencePage({
  data,
  open,
  newInvestigation,
  user,
}: {
  data: Data;
  open: (id: string) => void;
  newInvestigation: () => void;
  user: User;
}) {
  const [filter, setFilter] = useState("all");
  const invs = data.investigations.filter(
    (i) => filter === "all" || i.state === filter,
  );
  const m = data.operations.model;
  return (
    <>
      <div className="workflow-banner">
        <div>
          <span className="ai-orb small">
            <Sparkles size={20} />
          </span>
          <div>
            <h3>From observation to approved action</h3>
            <p>
              Local evidence workflow · every recommendation stays reviewable.
            </p>
          </div>
        </div>
        <div className="workflow-steps">
          {["Observe", "Retrieve", "Recommend", "Human review"].map((s, i) => (
            <span key={s}>
              <i>{i === 3 ? <ShieldCheck size={14} /> : <Check size={13} />}</i>
              {s}
              {i < 3 && <ChevronRight size={14} />}
            </span>
          ))}
        </div>
      </div>
      <div className="intelligence-layout">
        <section className="panel">
          <div className="table-toolbar">
            <div className="tabs">
              {[
                ["all", "All investigations"],
                ["awaiting_review", "To review"],
                ["approved", "Approved"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  className={filter === id ? "active" : ""}
                  onClick={() => setFilter(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="muted small-text">{invs.length} records</span>
          </div>
          <div className="investigation-list">
            {invs.map((inv) => (
              <button
                key={inv.id}
                className="investigation-card"
                onClick={() => open(inv.id)}
              >
                <span className="investigation-symbol">
                  <Workflow size={21} />
                </span>
                <div>
                  <div className="investigation-title">
                    <strong>{inv.title}</strong>
                    <Badge value={inv.state} />
                  </div>
                  <p>{inv.payload.recommendation}</p>
                  <div className="investigation-meta">
                    <span>
                      <Box size={12} />
                      {inv.asset_tag}
                    </span>
                    <span>
                      <FileCheck2 size={12} />
                      {inv.payload.evidence.length} sources
                    </span>
                    <span>Version {inv.version}</span>
                    <span>{age(inv.created)}</span>
                  </div>
                </div>
                <ChevronRight size={18} />
              </button>
            ))}
            {!invs.length && (
              <Empty
                icon={Sparkles}
                title="No investigations in this view"
                description="Start from an asset with current readings and applicable procedures."
                action={
                  <Button
                    onClick={newInvestigation}
                    disabled={
                      !["engineer", "planner", "admin"].includes(user.role)
                    }
                  >
                    Start an investigation
                  </Button>
                }
              />
            )}
          </div>
        </section>
        <aside>
          <section className="panel model-card">
            <span className="model-icon">
              <Cpu size={24} />
            </span>
            <h3>Condition intelligence</h3>
            <p>
              Working anomaly detection with a reproducible synthetic baseline.
            </p>
            <Badge value="healthy">{m.algorithm}</Badge>
            <div className="model-metrics">
              <div>
                <span>Synthetic F1</span>
                <strong>
                  {(m.f1 * 100).toFixed(1)}
                  <small>%</small>
                </strong>
              </div>
              <div>
                <span>Holdout samples</span>
                <strong>{m.evaluation_samples}</strong>
              </div>
            </div>
            <dl>
              <div>
                <dt>Training samples</dt>
                <dd>{m.training_samples.toLocaleString()}</dd>
              </div>
              <div>
                <dt>Precision / recall</dt>
                <dd>
                  {m.precision.toFixed(2)} / {m.recall.toFixed(2)}
                </dd>
              </div>
              <div>
                <dt>False positives</dt>
                <dd>
                  {m.false_positives} / {m.normal_samples}
                </dd>
              </div>
            </dl>
            <div className="model-disclaimer">
              <TriangleAlert size={15} />
              <p>
                Synthetic evaluation only. These results do not establish real
                industrial prediction accuracy.
              </p>
            </div>
          </section>
          <div className="review-note">
            <ShieldCheck size={19} />
            <h4>People remain in control.</h4>
            <p>
              The creator cannot approve their own recommendation. Change
              accounts to test independent review.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
