import { useState, useEffect } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CircleHelp,
  ClipboardCheck,
  ExternalLink,
  FileCheck2,
  FileText,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  Waves,
} from "lucide-react";
import {
  api,
  post,
  date,
  age,
  human,
  type User,
  type Investigation,
  type Evidence,
} from "../../api";

import { Badge, Button, Empty, Modal } from "../ui";
import { ConditionInvestigationOrigin } from "../ConditionInvestigationOrigin";
import type { Page, Run } from "../../types";
export function InvestigationModal({
  inv,
  user,
  busy,
  onClose,
  openDoc,
  run,
}: {
  inv: Investigation;
  user: User;
  busy: boolean;
  onClose: () => void;
  openDoc: (id: string, page?: number) => void;
  run: Run;
}) {
  const [tab, setTab] = useState("summary"),
    [reason, setReason] = useState(
      "Reviewed the observations, applicability and supporting evidence.",
    ),
    [reviewed, setReviewed] = useState(false),
    [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState(inv.payload.recommendation),
    [checklist, setChecklist] = useState(inv.payload.checklist.join("\n")),
    [due, setDue] = useState(
      new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    ),
    [assignee, setAssignee] = useState("Riya Patel");
  useEffect(() => {
    setReviewed(false);
    setEdit(false);
    setDraft(inv.payload.recommendation);
    setChecklist(inv.payload.checklist.join("\n"));
  }, [inv.id, inv.version]);
  const canDecide =
    ["approver", "admin"].includes(user.role) &&
    inv.creator_id !== user.id &&
    inv.state === "awaiting_review";
  const canEdit =
    ["engineer", "planner", "admin"].includes(user.role) &&
    inv.state !== "dispatched";
  async function decide(decision: string) {
    await run(
      () =>
        post(`/investigations/${inv.id}/decision`, {
          expected_version: inv.version,
          decision,
          reason,
        }),
      decision === "approve"
        ? "Recommendation approved for this exact version."
        : "Recommendation returned for revision.",
    );
  }
  return (
    <Modal
      wide
      title={inv.title}
      description={`${inv.asset_name} · ${inv.asset_tag} · Version ${inv.version}`}
      onClose={onClose}
    >
      <div className="investigation-statusbar">
        <Badge value={inv.state} />
        <span>
          Prepared by {inv.creator} · {age(inv.created)}
        </span>
        <span>
          <FileCheck2 size={13} />
          {inv.payload.evidence.length} evidence sources
        </span>
      </div>
      {inv.payload.condition_origin && <ConditionInvestigationOrigin origin={inv.payload.condition_origin} />}
      <div className="tabs modal-tabs">
        {[
          ["summary", "Findings & recommendation"],
          ["evidence", "Source evidence"],
          ["review", "Review & action"],
        ].map(([id, label]) => (
          <button
            className={tab === id ? "active" : ""}
            key={id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "summary" && (
        <>
          <div className="modal-section">
            <h3>
              <Waves size={17} />
              Observed facts
            </h3>
            {inv.payload.observations.map((f, i) => (
              <div className="fact-row" key={f}>
                <span>{i + 1}</span>
                <p>{f}</p>
              </div>
            ))}
          </div>
          <div className="modal-section">
            <h3>Possible explanations</h3>
            <div className="cause-chips">
              {inv.payload.possible_causes.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
            <p className="small-text muted">
              Hypotheses for review, not confirmed fault diagnoses.
            </p>
          </div>
          <div className="recommendation-block">
            <span className="eyebrow">
              <Sparkles size={13} />
              RECOMMENDATION
            </span>
            {edit ? (
              <>
                <label>
                  Maintenance recommendation
                  <textarea
                    rows={3}
                    minLength={10}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                </label>
                <label>
                  Inspection steps (one per line)
                  <textarea
                    rows={5}
                    value={checklist}
                    onChange={(e) => setChecklist(e.target.value)}
                  />
                </label>
              </>
            ) : (
              <>
                <h3>{inv.payload.recommendation}</h3>
                <ol className="checklist">
                  {inv.payload.checklist.map((s) => (
                    <li key={s}>
                      <CheckCircle2 size={16} />
                      <span>{s}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
            {canEdit && (
              <div className="edit-actions">
                {edit ? (
                  <>
                    <Button onClick={() => setEdit(false)}>Cancel edit</Button>
                    <Button
                      className="primary"
                      disabled={
                        busy || draft.trim().length < 10 || !checklist.trim()
                      }
                      onClick={() =>
                        run(
                          () =>
                            api(`/investigations/${inv.id}`, {
                              method: "PATCH",
                              body: JSON.stringify({
                                expected_version: inv.version,
                                recommendation: draft,
                                checklist: checklist
                                  .split("\n")
                                  .map((s) => s.trim())
                                  .filter(Boolean),
                              }),
                            }),
                          "New version saved. Previous approval invalidated.",
                        )
                      }
                    >
                      Save revised version
                    </Button>
                  </>
                ) : (
                  <Button
                    icon={SlidersHorizontal}
                    onClick={() => setEdit(true)}
                  >
                    Edit recommendation
                  </Button>
                )}
              </div>
            )}
          </div>
          <div className="data-gap">
            <TriangleAlert size={17} />
            <div>
              <strong>Evidence limits</strong>
              {inv.payload.data_gaps.map((g) => (
                <p key={g}>{g}</p>
              ))}
            </div>
          </div>
          <div className="modal-actions">
            <span className="small-text muted">{inv.payload.engine}</span>
            <Button className="primary" onClick={() => setTab("evidence")}>
              Review sources <ArrowRight size={15} />
            </Button>
          </div>
        </>
      )}
      {tab === "evidence" && (
        <>
          <div className="modal-section">
            <h3>Supporting procedures</h3>
            <p className="muted">
              Inspect the source page and confirm that the procedure applies to
              this equipment.
            </p>
            <div className="evidence-grid">
              {inv.payload.evidence.map((e) => (
                <div className="evidence-card" key={e.id}>
                  <div>
                    <FileText size={17} />
                    <strong>{e.title}</strong>
                  </div>
                  <p>{e.text}</p>
                  <span>
                    Page {e.page} · Version {e.version}
                  </span>
                  <Button
                    icon={ExternalLink}
                    onClick={() => openDoc(e.document_id, e.page)}
                  >
                    Open source document
                  </Button>
                </div>
              ))}
            </div>
            {!inv.payload.evidence.length && (
              <Empty
                title="No applicable evidence"
                description="Add an appropriate procedure before requesting approval."
                icon={BookOpen}
              />
            )}
          </div>
          <label className="evidence-attestation">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            I have reviewed the source evidence, applicability and limitations
            for this version.
          </label>
          <div className="modal-actions">
            <Button onClick={() => setTab("summary")}>Back to findings</Button>
            <Button className="primary" onClick={() => setTab("review")}>
              Continue to review <ArrowRight size={15} />
            </Button>
          </div>
        </>
      )}
      {tab === "review" && (
        <>
          <div className="review-summary">
            <ShieldCheck size={30} />
            <div>
              <h3>Controlled maintenance review</h3>
              <p>
                Approval binds version {inv.version}. Any material revision
                requires a new decision.
              </p>
            </div>
          </div>
          <div className="review-info-grid">
            <div>
              <span>Prepared by</span>
              <strong>{inv.creator}</strong>
            </div>
            <div>
              <span>Current state</span>
              <strong>{human(inv.state)}</strong>
            </div>
            <div>
              <span>Reviewed by</span>
              <strong>{inv.approver || "Pending independent review"}</strong>
            </div>
            <div>
              <span>Approval validity</span>
              <strong>
                {inv.approved_until
                  ? date(inv.approved_until, true) + " GST"
                  : "24 hours after approval"}
              </strong>
            </div>
          </div>
          {inv.decision_reason && (
            <div className="local-note">{inv.decision_reason}</div>
          )}
          {canDecide ? (
            <>
              <label>
                Decision reason
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  minLength={3}
                />
              </label>
              <label className="evidence-attestation">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                I reviewed the cited sources and this exact maintenance
                proposal.
              </label>
              <div className="modal-actions">
                <Button
                  className="danger"
                  disabled={busy || reason.length < 3}
                  onClick={() => decide("reject")}
                >
                  Return for revision
                </Button>
                <Button
                  className="primary"
                  icon={ShieldCheck}
                  disabled={
                    busy ||
                    !reviewed ||
                    reason.length < 3 ||
                    !inv.payload.evidence.length
                  }
                  onClick={() => decide("approve")}
                >
                  Approve version {inv.version}
                </Button>
              </div>
            </>
          ) : inv.state === "approved" &&
            ["planner", "admin"].includes(user.role) ? (
            <>
              <div className="form-grid">
                <label>
                  Due date
                  <input
                    type="date"
                    value={due}
                    onChange={(e) => setDue(e.target.value)}
                  />
                </label>
                <label>
                  Assigned technician
                  <input
                    value={assignee}
                    onChange={(e) => setAssignee(e.target.value)}
                  />
                </label>
              </div>
              <div className="modal-actions">
                <Button onClick={onClose}>Close</Button>
                <Button
                  className="primary"
                  icon={ClipboardCheck}
                  disabled={busy || !due}
                  onClick={() =>
                    run(async () => {
                      await post("/work-orders", {
                        investigation_id: inv.id,
                        expected_version: inv.version,
                        due_date: due,
                        assignee,
                      });
                      onClose();
                    }, "Work order planned from the approved recommendation.")
                  }
                >
                  Create work order
                </Button>
              </div>
            </>
          ) : (
            <div className="local-note">
              <CircleHelp size={17} />
              {inv.state === "awaiting_review"
                ? "Sign in as an independent Approver to review this draft. The creator cannot approve it."
                : inv.state === "approved"
                  ? "Sign in as a Planner to create a work order from this approval."
                  : inv.state === "dispatched"
                    ? "A work order has been created. Track execution in Work orders."
                    : "A permitted engineer can revise this recommendation and request another review."}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
