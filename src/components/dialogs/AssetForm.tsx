import { useState } from "react";
import { CircleHelp, Plus } from "lucide-react";
import { type User } from "../../api";

import { Button, Modal } from "../ui";

export function AssetForm({
  user,
  onClose,
  onSubmit,
  busy,
}: {
  user: User;
  onClose: () => void;
  onSubmit: (body: unknown) => Promise<boolean>;
  busy: boolean;
}) {
  const [form, setForm] = useState({
    tag: "",
    name: "",
    kind: "Pump",
    site: user.sites[0],
    location: "",
    criticality: "High",
    threshold: 4.5,
  });
  return (
    <Modal
      title="Register an asset"
      description="Create the equipment record before ingesting measurements."
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(form);
        }}
        className="form-grid"
      >
        <label>
          Equipment tag
          <input
            required
            minLength={2}
            maxLength={40}
            pattern="[A-Za-z0-9_-]+"
            placeholder="P-110"
            value={form.tag}
            onChange={(e) => setForm({ ...form, tag: e.target.value })}
          />
        </label>
        <label>
          Equipment type
          <select
            value={form.kind}
            onChange={(e) => setForm({ ...form, kind: e.target.value })}
          >
            {["Pump", "Compressor", "Motor", "Turbine"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="full-span">
          Equipment name
          <input
            required
            minLength={3}
            placeholder="Cooling water circulation pump"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label>
          Site
          <select
            value={form.site}
            onChange={(e) => setForm({ ...form, site: e.target.value })}
          >
            {user.sites.map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Unit / location
          <input
            required
            minLength={2}
            placeholder="Utilities · Loop B"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
          />
        </label>
        <label>
          Criticality
          <select
            value={form.criticality}
            onChange={(e) => setForm({ ...form, criticality: e.target.value })}
          >
            {["Critical", "High", "Medium", "Low"].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Demo vibration limit (mm/s)
          <input
            type="number"
            step="0.1"
            min="0.1"
            max="100"
            value={form.threshold}
            onChange={(e) =>
              setForm({ ...form, threshold: Number(e.target.value) })
            }
          />
        </label>
        <div className="local-note full-span">
          <CircleHelp size={17} />
          New assets start without readings. Use the telemetry API to connect a
          data source.
        </div>
        <div className="modal-actions full-span">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button className="primary" type="submit" disabled={busy} icon={Plus}>
            {busy ? "Registering…" : "Register asset"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
