import { useState } from "react";
import { Sparkles } from "lucide-react";
import { type Asset, type Evidence } from "../../api";

import { Button, Modal } from "../ui";

export function NewInvestigation({
  assets,
  onClose,
  onSubmit,
  busy,
}: {
  assets: Asset[];
  onClose: () => void;
  onSubmit: (id: string) => Promise<boolean>;
  busy: boolean;
}) {
  const [id, setId] = useState(
    [...assets].sort((a, b) => (a.health ?? 100) - (b.health ?? 100))[0]?.id ||
      "",
  );
  return (
    <Modal
      title="Start an investigation"
      description="Collect current observations and applicable document evidence."
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(id);
        }}
      >
        <label>
          Equipment
          <select value={id} onChange={(e) => setId(e.target.value)} required>
            {assets.map((a) => (
              <option key={a.id} value={a.id}>
                {a.tag} · {a.name} {a.reading ? "" : "(no readings)"}
              </option>
            ))}
          </select>
        </label>
        <div className="investigate-preview">
          {[
            ["Observation", "Read the current four-channel snapshot."],
            ["Evidence", "Retrieve authorized, applicable procedures."],
            ["Recommendation", "Prepare a draft with source citations."],
            ["Human review", "Keep maintenance actions behind approval."],
          ].map(([a, b], i) => (
            <div key={a}>
              <span>{i + 1}</span>
              <div>
                <strong>{a}</strong>
                <p>{b}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="local-note">
          <Sparkles size={17} />
          Local deterministic workflow. No external LLM key is required.
        </div>
        <div className="modal-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="primary"
            icon={Sparkles}
            type="submit"
            disabled={busy || !id}
          >
            {busy ? "Collecting evidence…" : "Prepare investigation"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
