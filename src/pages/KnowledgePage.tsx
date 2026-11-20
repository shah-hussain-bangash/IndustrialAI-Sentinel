import { useState, useEffect, type FormEvent } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  FileText,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import { post, type DocumentInfo, type Evidence } from "../api";

import { Badge, Button, Empty, Spinner } from "../components/ui";
import type { Page } from "../types";
export function KnowledgePage({
  documents,
  openDoc,
  site,
}: {
  documents: DocumentInfo[];
  openDoc: (id: string, page?: number) => void;
  site: string;
}) {
  const [query, setQuery] = useState(""),
    [asked, setAsked] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [answer, setAnswer] = useState<{
      answer: string;
      evidence: Evidence[];
      engine: string;
    } | null>(null);
  async function ask(e?: FormEvent) {
    e?.preventDefault();
    if (query.trim().length < 3) return;
    setLoading(true);
    setError("");
    setAsked(true);
    try {
      setAnswer(
        await post("/knowledge/ask", { question: query, site: site || null }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    setAnswer(null);
    setAsked(false);
  }, [site]);
  return (
    <>
      <section className="knowledge-hero">
        <div className="knowledge-decoration">
          <BookOpen size={85} />
          <span />
          <span />
        </div>
        <div className="eyebrow">
          <Sparkles size={13} /> YOUR AUTHORIZED KNOWLEDGE
        </div>
        <h2>
          The right evidence.
          <br />
          Within reach.
        </h2>
        <p>
          Search procedures, inspect the source and understand its
          applicability.
        </p>
        <form className="knowledge-search" onSubmit={ask}>
          <Search size={20} />
          <input
            aria-label="Ask your industrial knowledge base"
            placeholder="What should I review for elevated pump vibration?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button
            type="submit"
            className="primary"
            disabled={loading || query.trim().length < 3}
          >
            {loading ? (
              <Loader2 className="spin" size={17} />
            ) : (
              <ArrowRight size={19} />
            )}
            <span className="sr-only">Search knowledge</span>
          </Button>
        </form>
        <div className="suggested-queries">
          Try:{" "}
          {[
            "Pump vibration inspection",
            "Work order approval",
            "Missing sensor readings",
          ].map((q) => (
            <button key={q} onClick={() => setQuery(q)}>
              {q}
              <ArrowUpRight size={11} />
            </button>
          ))}
        </div>
      </section>
      {asked && (
        <section className="panel search-answer">
          <div className="panel-header">
            <h2>
              <Sparkles size={18} />
              Evidence matches
            </h2>
            <Badge value="healthy">Local retrieval</Badge>
          </div>
          {loading ? (
            <Spinner />
          ) : error ? (
            <p className="form-error">{error}</p>
          ) : (
            answer && (
              <>
                <p>{answer.answer}</p>
                <div className="evidence-grid">
                  {answer.evidence.map((e) => (
                    <button
                      className="evidence-card"
                      key={e.id}
                      onClick={() => openDoc(e.document_id, e.page)}
                    >
                      <div>
                        <FileText size={17} />
                        <strong>{e.title}</strong>
                        <ArrowUpRight size={14} />
                      </div>
                      <p>{e.text}</p>
                      <span>
                        Page {e.page} · Version {e.version} · {e.kind}
                      </span>
                    </button>
                  ))}
                </div>
                <small className="muted">
                  {answer.engine}. No external model call is made.
                </small>
              </>
            )
          )}
        </section>
      )}
      <div className="section-heading">
        <div>
          <h2>
            Document library{" "}
            <span className="count-pill">{documents.length}</span>
          </h2>
          <p>Text-based PDFs and procedures, scoped to your permitted sites.</p>
        </div>
        <span className="small-text muted">
          <ShieldCheck size={14} /> Permission-aware retrieval
        </span>
      </div>
      <div className="document-grid">
        {documents.map((d) => (
          <button
            className="document-card"
            key={d.id}
            onClick={() => openDoc(d.id)}
          >
            <div className="document-card-top">
              <span className="document-icon">
                <FileText size={26} />
              </span>
              <span className="file-type">
                {d.filename.split(".").at(-1)?.toUpperCase()}
              </span>
            </div>
            <h3>{d.title}</h3>
            <p>
              {d.kind} <span>·</span> Version {d.version}
            </p>
            <span
              className={`original-label ${d.original_available ? "archived" : "legacy"}`}
            >
              {d.original_available
                ? "Original archived"
                : "Extracted text only"}
            </span>
            <div className="document-preview">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="document-footer">
              <span>
                {d.page_count} pages · {d.site.split(" ")[0]}
              </span>
              <ArrowUpRight size={16} />
            </div>
          </button>
        ))}
      </div>
      {!documents.length && (
        <Empty
          icon={BookOpen}
          title="Your library is empty"
          description="Upload an applicable text-based procedure to start evidence retrieval."
        />
      )}
    </>
  );
}
