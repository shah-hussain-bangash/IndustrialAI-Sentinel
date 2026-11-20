import { useState, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  Download,
  ShieldCheck,
} from "lucide-react";
import { api } from "../../api";

import { Spinner, Modal, Button } from "../ui";
import type { Page } from "../../types";
export function DocumentViewer({
  id,
  initialPage = 1,
  onClose,
}: {
  id: string;
  initialPage?: number;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<{
      title: string;
      version: string;
      pages: string[];
      site: string;
      kind: string;
      checksum: string;
      filename: string;
      original_available: boolean;
      original_bytes: number | null;
    } | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState(Math.max(0, initialPage - 1));
  const [downloading, setDownloading] = useState(false),
    [downloadError, setDownloadError] = useState("");
  async function downloadOriginal() {
    if (!doc || downloading) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(id)}/original`,
        { credentials: "same-origin" },
      );
      if (!response.ok) {
        if (response.status === 401)
          window.dispatchEvent(new Event("session-expired"));
        const failure = await response
          .json()
          .catch(() => ({ detail: "Original file could not be downloaded." }));
        throw new Error(
          typeof failure.detail === "string"
            ? failure.detail
            : "Original file could not be downloaded.",
        );
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setDownloadError((e as Error).message);
    } finally {
      setDownloading(false);
    }
  }
  useEffect(() => {
    api<typeof doc>("/documents/" + id)
      .then(setDoc)
      .catch((e) => setError(e.message));
  }, [id]);
  return (
    <Modal
      wide
      title={doc?.title || "Source document"}
      description={
        doc
          ? `${doc.site} · ${doc.kind} · Version ${doc.version}`
          : "Checking document access…"
      }
      onClose={onClose}
    >
      {error ? (
        <p className="form-error">{error}</p>
      ) : !doc ? (
        <Spinner />
      ) : (
        <>
          <div className="original-access">
            <div>
              <strong>
                {doc.original_available
                  ? "Original file archived"
                  : "Original file not retained"}
              </strong>
              <p>
                {doc.original_available
                  ? `${doc.filename} · ${((doc.original_bytes || 0) / 1024).toFixed(1)} KiB · checksum verified before download`
                  : "This earlier record contains extracted text only. Upload the source again as a new document to retain its original bytes."}
              </p>
            </div>
            {doc.original_available && (
              <Button
                icon={Download}
                disabled={downloading}
                onClick={downloadOriginal}
              >
                {downloading ? "Checking file…" : "Download original"}
              </Button>
            )}
          </div>
          {downloadError && (
            <p className="form-error" role="alert">
              {downloadError}
            </p>
          )}
          <div className="source-toolbar">
            <span>
              <FileCheck2 size={15} />
              Extracted source text
            </span>
            <div>
              <button
                className="icon-btn"
                aria-label="Previous page"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                Page {page + 1} of {doc.pages.length}
              </span>
              <button
                className="icon-btn"
                aria-label="Next page"
                disabled={page >= doc.pages.length - 1}
                onClick={() => setPage(page + 1)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
          <article className="source-page">
            <div className="eyebrow">SOURCE EVIDENCE · PAGE {page + 1}</div>
            <h3>{doc.title}</h3>
            <p>{doc.pages[page]}</p>
          </article>
          <div className="local-note">
            <ShieldCheck size={16} />
            Access checked on open. Confirm equipment applicability and document
            quality before use.
          </div>
          <p className="checksum">SHA-256: {doc.checksum}</p>
        </>
      )}
    </Modal>
  );
}
