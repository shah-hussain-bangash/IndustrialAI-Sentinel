import { useState } from "react";
import { ShieldCheck, Upload } from "lucide-react";
import { type User } from "../../api";

import { Button, Modal } from "../ui";

export function UploadDocument({
  user,
  site,
  onClose,
  onSubmit,
  busy,
}: {
  user: User;
  site: string;
  onClose: () => void;
  onSubmit: (form: FormData) => Promise<boolean>;
  busy: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <Modal
      title="Add a knowledge source"
      description="Upload a text-based PDF or UTF-8 text file, up to 10 MB."
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!file) return;
          const form = new FormData(e.currentTarget);
          form.set("file", file);
          onSubmit(form);
        }}
      >
        <label className="upload-zone">
          <Upload size={30} />
          <strong>{file?.name || "Choose a procedure or manual"}</strong>
          <span>PDF, TXT or MD · original retained with extracted text</span>
          <input
            type="file"
            accept=".pdf,.txt,.md"
            required
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <div className="form-grid">
          <label className="full-span">
            Document title
            <input
              name="title"
              minLength={3}
              maxLength={200}
              required
              placeholder="Equipment inspection procedure"
            />
          </label>
          <label>
            Site
            <select name="site" defaultValue={site || user.sites[0]}>
              {user.sites.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Applies to
            <select name="kind">
              {["All equipment", "Pump", "Compressor", "Motor", "Turbine"].map(
                (k) => (
                  <option key={k}>{k}</option>
                ),
              )}
            </select>
          </label>
        </div>
        <div className="local-note">
          <ShieldCheck size={16} />
          Upload only documents you are permitted to use. Scanned PDFs need OCR
          before upload. Original file bytes are stored privately with the
          document.
        </div>
        <div className="modal-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="primary"
            type="submit"
            disabled={busy || !file}
            icon={Upload}
          >
            {busy ? "Extracting text…" : "Add to knowledge base"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
