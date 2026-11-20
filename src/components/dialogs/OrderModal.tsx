import { useState } from "react";
import {
  CheckCheck,
  RefreshCw,
  Send,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { post, date, type User, type WorkOrder } from "../../api";

import { Badge, Button, Modal } from "../ui";
import type { Run } from "../../types";
export function OrderModal({
  order,
  user,
  busy,
  onClose,
  run,
}: {
  order: WorkOrder;
  user: User;
  busy: boolean;
  onClose: () => void;
  run: Run;
}) {
  const [outcome, setOutcome] = useState(""),
    [timeout, setTimeoutSim] = useState(false);
  const planner = ["planner", "admin"].includes(user.role),
    technician = ["technician", "admin", "planner"].includes(user.role);
  return (
    <Modal
      title={order.reference}
      description={`${order.asset_tag} · ${order.asset_name}`}
      onClose={onClose}
    >
      <div className="order-detail-title">
        <Badge value={order.status} />
        <Badge value={order.priority === "High" ? "warning" : "neutral"}>
          {order.priority} priority
        </Badge>
        <h3>{order.title}</h3>
      </div>
      <dl className="order-details">
        <div>
          <dt>Assigned to</dt>
          <dd>{order.assignee}</dd>
        </div>
        <div>
          <dt>Due date</dt>
          <dd>{order.due_date}</dd>
        </div>
        <div>
          <dt>Integration</dt>
          <dd>Local CMMS simulator</dd>
        </div>
        <div>
          <dt>External reference</dt>
          <dd>{order.external_ref || "Not confirmed"}</dd>
        </div>
        <div>
          <dt>Record version</dt>
          <dd>{order.version}</dd>
        </div>
      </dl>
      {order.outcome && (
        <div className="outcome">
          <h4>Recorded findings / reason</h4>
          <p>{order.outcome}</p>
        </div>
      )}
      {order.status === "planned" && planner && (
        <>
          <label className="toggle-row">
            <span>
              <strong>Test uncertain response</strong>
              <small>
                Simulator accepts the order, then requires reconciliation.
              </small>
            </span>
            <input
              type="checkbox"
              checked={timeout}
              onChange={(e) => setTimeoutSim(e.target.checked)}
            />
          </label>
          <div className="modal-actions">
            <Button onClick={onClose}>Close</Button>
            <Button
              className="primary"
              disabled={busy}
              icon={Send}
              onClick={() =>
                run(
                  () =>
                    post(`/work-orders/${order.id}/dispatch`, {
                      expected_version: order.version,
                      simulate_timeout: timeout,
                    }),
                  timeout
                    ? "Simulator accepted the order. Reconcile to confirm its reference."
                    : "Work order dispatched to the local simulator.",
                )
              }
            >
              Dispatch to simulator
            </Button>
          </div>
        </>
      )}
      {order.status === "reconciling" && (
        <>
          <div className="local-note">
            <TriangleAlert size={17} />
            Do not create another order. Look up the accepted command and bind
            the existing reference.
          </div>
          <div className="modal-actions">
            <Button
              className="primary"
              icon={RefreshCw}
              disabled={busy || !planner}
              onClick={() =>
                run(
                  () =>
                    post(`/work-orders/${order.id}/reconcile`, {
                      expected_version: order.version,
                    }),
                  "Existing simulator order reconciled. No duplicate was created.",
                )
              }
            >
              Reconcile existing order
            </Button>
          </div>
        </>
      )}
      {["planned", "in_progress"].includes(order.status) && (
        <div className="modal-section">
          <label>
            {order.status === "in_progress"
              ? "Actual findings or cancellation reason"
              : "Cancellation reason"}
            <textarea
              rows={3}
              placeholder="Record what was actually observed. Do not copy a hypothesis as a confirmed fault."
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            />
          </label>
          <div className="modal-actions">
            <Button
              className="danger"
              disabled={busy || !planner || outcome.trim().length < 5}
              onClick={() =>
                run(
                  () =>
                    post(`/work-orders/${order.id}/transition`, {
                      expected_version: order.version,
                      status: "cancelled",
                      outcome,
                    }),
                  "Cancellation confirmed in the local workflow.",
                )
              }
            >
              Cancel order
            </Button>
            {order.status === "in_progress" && (
              <Button
                className="primary"
                icon={CheckCheck}
                disabled={busy || !technician || outcome.trim().length < 10}
                onClick={() =>
                  run(
                    () =>
                      post(`/work-orders/${order.id}/transition`, {
                        expected_version: order.version,
                        status: "completed",
                        outcome,
                      }),
                    "Work completed and findings recorded.",
                  )
                }
              >
                Record completion
              </Button>
            )}
          </div>
        </div>
      )}
      {!planner && order.status === "planned" && (
        <div className="local-note">
          <ShieldCheck size={17} />A Planner account can dispatch or cancel this
          order.
        </div>
      )}
    </Modal>
  );
}
