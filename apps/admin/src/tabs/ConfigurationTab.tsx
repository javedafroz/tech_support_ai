import { useCallback, useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { authHeaders } from "../auth";
import Badge from "../components/Badge";
import Drawer from "../components/Drawer";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";

export type MeResponse = {
  subject: string;
  username: string | null;
  email: string | null;
  roles: string[];
  can_edit: boolean;
  can_publish: boolean;
};

type DocumentItem = {
  id: string;
  title: string;
  slug: string;
  status: string;
  source_content_type: string;
  version: number;
  chunk_count: number | null;
  converter_name: string | null;
  updated_at: string;
};

type DocumentList = {
  items: DocumentItem[];
  total: number;
};

type SearchHit = {
  document_id: string;
  title: string;
  section_title: string | null;
  score: number;
  excerpt: string;
};

type Props = {
  me: MeResponse | null;
};

function statusBadge(status: string) {
  if (status === "published") return <Badge variant="success">published</Badge>;
  if (status === "draft") return <Badge variant="neutral">draft</Badge>;
  if (status === "failed") return <Badge variant="danger">{status}</Badge>;
  return <Badge variant="warning">{status}</Badge>;
}

function typeLabel(contentType: string): string {
  if (contentType.includes("pdf")) return "PDF";
  if (contentType.includes("markdown") || contentType.includes("md")) return "MD";
  return contentType.split("/").pop()?.toUpperCase() || "FILE";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ConfigurationTab({ me }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocumentList | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("network");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<DocumentItem | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [query, setQuery] = useState("VPN disconnects DPD timeout");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = await authHeaders();
      const docsRes = await fetch("/api/v1/admin/kb/documents", { headers });
      if (!docsRes.ok) throw new Error(`/documents failed: ${docsRes.status} ${await docsRes.text()}`);
      setDocs((await docsRes.json()) as DocumentList);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function acceptFile(next: File | null) {
    if (!next) return;
    const name = next.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".md") && !next.type.includes("pdf") && !next.type.includes("markdown")) {
      setError("Choose a PDF or Markdown file");
      return;
    }
    setFile(next);
    setError(null);
    if (!title.trim()) {
      setTitle(next.name.replace(/\.(pdf|md)$/i, ""));
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0] ?? null;
    acceptFile(dropped);
  }

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF or Markdown file");
      return;
    }
    setLoading(true);
    setBusy("Uploading & ingesting…");
    setError(null);
    try {
      const headers = await authHeaders();
      const body = new FormData();
      body.append("file", file);
      if (title.trim()) body.append("title", title.trim());
      if (tags.trim()) body.append("category_tags", tags.trim());
      const res = await fetch("/api/v1/admin/kb/documents", {
        method: "POST",
        headers,
        body,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
      const doc = (await res.json()) as DocumentItem;
      setFile(null);
      setTitle("");
      await load();
      await openMarkdown(doc);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setBusy(null);
    }
  }

  async function openMarkdown(doc: DocumentItem) {
    setPreviewDoc(doc);
    setMarkdown(null);
    try {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/admin/kb/documents/${doc.id}/markdown`, { headers });
      if (!res.ok) throw new Error(`Markdown preview failed: ${res.status} ${await res.text()}`);
      const data = (await res.json()) as { markdown: string };
      setMarkdown(data.markdown);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPreviewDoc(null);
    }
  }

  async function publish(id: string) {
    setLoading(true);
    setBusy("Publishing…");
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/admin/kb/documents/${id}/publish`, {
        method: "POST",
        headers,
      });
      if (!res.ok) throw new Error(`Publish failed: ${res.status} ${await res.text()}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setBusy(null);
    }
  }

  async function reindex(id: string) {
    setLoading(true);
    setBusy("Reindexing…");
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/admin/kb/documents/${id}/reindex`, {
        method: "POST",
        headers,
      });
      if (!res.ok) throw new Error(`Reindex failed: ${res.status} ${await res.text()}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setBusy(null);
    }
  }

  async function remove(id: string, docTitle: string) {
    if (!window.confirm(`Delete "${docTitle}"? This removes it from storage and the vector index.`)) {
      return;
    }
    setLoading(true);
    setBusy("Deleting…");
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/admin/kb/documents/${id}`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok && res.status !== 204) {
        throw new Error(`Delete failed: ${res.status} ${await res.text()}`);
      }
      if (previewDoc?.id === id) {
        setPreviewDoc(null);
        setMarkdown(null);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setBusy(null);
    }
  }

  async function runSearch(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setBusy("Searching…");
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch("/api/v1/admin/kb/search/preview", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 5 }),
      });
      if (!res.ok) throw new Error(`Search failed: ${res.status} ${await res.text()}`);
      const data = (await res.json()) as { hits: SearchHit[]; note?: string };
      setHits(data.hits);
      if (data.note) setError(data.note);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setBusy(null);
    }
  }

  return (
    <>
      {busy ? (
        <div className="top-progress" aria-hidden="true">
          <span />
        </div>
      ) : null}

      <PageHeader
        title="Configuration"
        subtitle="Upload agent handbooks, publish them into the vector index, and preview retrieval."
        actions={
          <button className="btn secondary" type="button" onClick={() => void load()} disabled={loading}>
            Refresh
          </button>
        }
      />

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Upload handbook</h2>
          {busy ? <span className="muted" style={{ fontSize: "0.8125rem" }}>{busy}</span> : null}
        </div>
        <div className="card-body">
          <form onSubmit={(e) => void onUpload(e)}>
            <div
              className={`dropzone ${dragOver ? "active" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
              }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.6">
                <path d="M12 16V4M12 4l-4 4M12 4l4 4" />
                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              </svg>
              <p className="dropzone-title">Drop a PDF or Markdown file here</p>
              <p className="dropzone-hint">or click to browse · PDFs convert via Docling</p>
              {file ? (
                <span className="file-chip" onClick={(e) => e.stopPropagation()}>
                  {file.name}
                  <button
                    type="button"
                    className="btn ghost sm"
                    style={{ color: "#64748b", border: "none", padding: "0 0.2rem" }}
                    onClick={() => setFile(null)}
                    aria-label="Remove file"
                  >
                    ×
                  </button>
                </span>
              ) : null}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.md,text/markdown,application/pdf"
                hidden
                onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="doc-title">Title</label>
                <input
                  id="doc-title"
                  className="input"
                  type="text"
                  placeholder="Optional — defaults from filename"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="doc-tags">Tags</label>
                <input
                  id="doc-tags"
                  className="input"
                  type="text"
                  placeholder="Comma-separated, e.g. network,vpn"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                />
              </div>
            </div>

            <div className="row" style={{ marginTop: "1rem" }}>
              <button className="btn" type="submit" disabled={loading || !file}>
                {busy?.startsWith("Uploading") ? <span className="spinner" /> : null}
                Upload & ingest
              </button>
            </div>
          </form>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Documents</h2>
          {docs ? <span className="muted" style={{ fontSize: "0.8125rem" }}>{docs.total} total</span> : null}
        </div>
        <div className="card-body flush">
          {docs && docs.total === 0 ? (
            <EmptyState
              title="No handbooks yet"
              description="Upload a PDF or Markdown handbook to get started."
            />
          ) : docs && docs.total > 0 ? (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Type</th>
                    <th>Chunks</th>
                    <th>Updated</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {docs.items.map((doc) => (
                    <tr key={doc.id}>
                      <td>
                        <strong>{doc.title}</strong>
                        <div className="muted" style={{ fontSize: "0.75rem" }}>
                          v{doc.version}
                        </div>
                      </td>
                      <td>{statusBadge(doc.status)}</td>
                      <td>
                        <Badge variant="neutral">{typeLabel(doc.source_content_type)}</Badge>
                      </td>
                      <td>{doc.chunk_count ?? "—"}</td>
                      <td className="muted" style={{ fontSize: "0.8125rem" }}>
                        {formatDate(doc.updated_at)}
                      </td>
                      <td>
                        <div className="row-actions">
                          <button className="btn secondary sm" type="button" onClick={() => void openMarkdown(doc)}>
                            Preview
                          </button>
                          <button className="btn secondary sm" type="button" onClick={() => void reindex(doc.id)}>
                            Reindex
                          </button>
                          {me?.can_publish && doc.status !== "published" ? (
                            <button className="btn sm" type="button" onClick={() => void publish(doc.id)}>
                              Publish
                            </button>
                          ) : null}
                          {me?.can_publish ? (
                            <button
                              className="btn danger sm"
                              type="button"
                              onClick={() => void remove(doc.id, doc.title)}
                            >
                              Delete
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: "1.5rem" }}>
              <span className="spinner" />
            </div>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Retrieval preview</h2>
        </div>
        <div className="card-body">
          <form onSubmit={(e) => void runSearch(e)} className="row">
            <div className="search-field">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" />
              </svg>
              <input
                className="input"
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search published handbooks…"
              />
            </div>
            <button className="btn" type="submit" disabled={loading}>
              Search
            </button>
          </form>

          {hits.length === 0 ? (
            <p className="muted" style={{ marginTop: "1rem", marginBottom: 0, fontSize: "0.875rem" }}>
              Run a search against published handbooks to validate retrieval quality.
            </p>
          ) : (
            <div className="result-list">
              {hits.map((hit) => (
                <div key={`${hit.document_id}-${hit.score}-${hit.excerpt.slice(0, 12)}`} className="result-card">
                  <div className="result-card-top">
                    <div>
                      <strong>{hit.title}</strong>
                      {hit.section_title ? (
                        <span className="muted" style={{ marginLeft: "0.5rem", fontSize: "0.8125rem" }}>
                          {hit.section_title}
                        </span>
                      ) : null}
                    </div>
                    <Badge variant="info">score {hit.score.toFixed(3)}</Badge>
                  </div>
                  <p className="result-excerpt">{hit.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <Drawer
        open={Boolean(previewDoc)}
        title={previewDoc?.title ?? "Markdown preview"}
        subtitle={
          previewDoc ? `${previewDoc.status} · ${typeLabel(previewDoc.source_content_type)}` : undefined
        }
        onClose={() => {
          setPreviewDoc(null);
          setMarkdown(null);
        }}
      >
        {markdown === null ? (
          <div className="row" style={{ justifyContent: "center", padding: "2rem" }}>
            <span className="spinner" />
          </div>
        ) : (
          <pre className="markdown-preview">{markdown}</pre>
        )}
      </Drawer>
    </>
  );
}
