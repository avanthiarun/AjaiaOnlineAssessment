import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type DocumentList, type DocumentSummary, type ImportInfo } from "../api/client";
import { DocumentRow } from "../components/DocumentRow";
import { TopBar } from "../components/TopBar";

// Shown until /api/documents/import/info answers, or if it fails; the server is the source of truth.
const DEFAULT_IMPORT_INFO: ImportInfo = {
  extensions: [".txt", ".md", ".docx", ".odt", ".rtf", ".html", ".htm", ".pdf"],
  max_mb: 5,
};
const FORMAT_NOTE = "Formatting is kept for .docx, .odt, .md and .html; .rtf and .pdf import as plain text.";

/** "a, b and c" */
function joinWithAnd(items: string[]): string {
  return items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function uploadHint({ extensions, max_mb }: ImportInfo): string {
  const shown = extensions.filter((ext) => ext !== ".htm"); // .htm is just an alias of .html
  return `Supports ${joinWithAnd(shown)} up to ${max_mb} MB. ${FORMAT_NOTE}`;
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

const byNewest = (a: DocumentSummary, b: DocumentSummary) => b.updated_at.localeCompare(a.updated_at);

export function HomePage() {
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const [docs, setDocs] = useState<DocumentList | null>(null);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState<"creating" | "uploading" | null>(null);
  const [startError, setStartError] = useState("");
  const [importInfo, setImportInfo] = useState<ImportInfo>(DEFAULT_IMPORT_INFO);

  const load = useCallback(async () => {
    setDocs(null);
    setLoadError("");
    try {
      setDocs(await api.listDocuments());
    } catch (err) {
      setLoadError(errorMessage(err, "Could not load your documents."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    api
      .importInfo()
      .then(setImportInfo)
      .catch(() => setImportInfo(DEFAULT_IMPORT_INFO));
  }, []);

  async function createBlank() {
    setBusy("creating");
    setStartError("");
    try {
      const doc = await api.createDocument();
      navigate(`/d/${doc.id}`);
    } catch (err) {
      setStartError(errorMessage(err, "Could not create a document."));
      setBusy(null);
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow picking the same file again after an error
    if (!file) return;
    setBusy("uploading");
    setStartError("");
    try {
      const doc = await api.importDocument(file);
      navigate(`/d/${doc.id}`);
    } catch (err) {
      setStartError(errorMessage(err, "Upload failed."));
      setBusy(null);
    }
  }

  async function rename(id: string, title: string) {
    setActionError("");
    try {
      const updated = await api.updateDocument(id, { title });
      setDocs((current) =>
        current && {
          ...current,
          owned: current.owned.map((d) => (d.id === id ? { ...d, ...updated } : d)).sort(byNewest),
        },
      );
    } catch (err) {
      setActionError(errorMessage(err, "Could not rename the document."));
    }
  }

  async function remove(id: string) {
    setActionError("");
    try {
      await api.deleteDocument(id);
      setDocs((current) => current && { ...current, owned: current.owned.filter((d) => d.id !== id) });
    } catch (err) {
      setActionError(errorMessage(err, "Could not delete the document."));
    }
  }

  async function leave(id: string) {
    setActionError("");
    try {
      await api.leaveDocument(id);
      setDocs((current) => current && { ...current, shared: current.shared.filter((d) => d.id !== id) });
    } catch (err) {
      setActionError(errorMessage(err, "Could not leave the document."));
    }
  }

  return (
    <>
      <TopBar />
      <section className="start-section">
        <div className="home-container">
          <h2 className="section-label">Start a new document</h2>
          <div className="tiles">
            <button className="tile" onClick={() => void createBlank()} disabled={busy !== null}>
              <span className="tile-page tile-blank">
                <span className="plus" aria-hidden="true">+</span>
              </span>
              <span className="tile-label">{busy === "creating" ? "Creating…" : "Blank document"}</span>
            </button>
            <div>
              <button className="tile" onClick={() => fileInput.current?.click()} disabled={busy !== null}>
                <span className="tile-page tile-upload">
                  {busy === "uploading" ? <span className="spinner" aria-hidden="true" /> : <span aria-hidden="true">⤒</span>}
                </span>
                <span className="tile-label">{busy === "uploading" ? "Uploading…" : "Upload file"}</span>
              </button>
              <input ref={fileInput} type="file" accept={importInfo.extensions.join(",")} hidden onChange={(e) => void handleUpload(e)} />
            </div>
          </div>
          <p className="muted small">{uploadHint(importInfo)}</p>
          {startError && (
            <p className="form-error" role="alert">
              {startError}
            </p>
          )}
        </div>
      </section>

      <main className="home-container">
        {actionError && (
          <div className="banner banner-error" role="alert">
            {actionError}
          </div>
        )}
        {loadError ? (
          <div className="banner banner-error" role="alert">
            {loadError}
            <button className="btn" onClick={() => void load()}>
              Retry
            </button>
          </div>
        ) : (
          <>
            <DocSection title="Owned by me" docs={docs?.owned} empty="You have no documents yet. Create one above.">
              {(doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  onRename={(title) => rename(doc.id, title)}
                  onDelete={() => remove(doc.id)}
                />
              )}
            </DocSection>
            <DocSection title="Shared with me" docs={docs?.shared} empty="Nothing has been shared with you yet.">
              {(doc) => <DocumentRow key={doc.id} doc={doc} shared onLeave={() => leave(doc.id)} />}
            </DocSection>
          </>
        )}
      </main>
    </>
  );
}

interface DocSectionProps {
  title: string;
  docs: DocumentSummary[] | undefined;
  empty: string;
  children: (doc: DocumentSummary) => JSX.Element;
}

/** A titled list that shows a skeleton while loading and a message when empty. */
function DocSection({ title, docs, empty, children }: DocSectionProps) {
  return (
    <section className="doc-section">
      <h2 className="section-label">{title}</h2>
      {docs === undefined ? (
        <ul className="doc-list" aria-busy="true" aria-label={`Loading ${title}`}>
          {[0, 1, 2].map((i) => (
            <li key={i} className="doc-row skeleton-row">
              <span className="skeleton" />
            </li>
          ))}
        </ul>
      ) : docs.length === 0 ? (
        <p className="empty-state">{empty}</p>
      ) : (
        <ul className="doc-list">{docs.map(children)}</ul>
      )}
    </section>
  );
}
