import { documentFileUrl } from "../../lib/api";

interface Props {
  docId: string | null;
  title: string | null;
  mode: "large" | "small";
  onToggle: () => void;
}

function textbookEmbedUrl(docId: string): string {
  const base = documentFileUrl(docId);
  return `${base}#toolbar=0&navpanes=0&view=FitH&zoom=page-width`;
}

export default function TextbookOverlay({
  docId,
  title,
  mode,
  onToggle,
}: Props) {
  if (!docId) return null;

  if (mode === "small") {
    return (
      <button
        type="button"
        className="textbook-overlay textbook-overlay-small"
        onClick={onToggle}
        aria-label={`Open textbook${title ? `: ${title}` : ""}`}
        title={title ?? "Open textbook"}
      >
        <DocIcon />
      </button>
    );
  }

  const src = textbookEmbedUrl(docId);
  return (
    <section
      className="textbook-overlay textbook-overlay-large"
      aria-label="Textbook"
    >
      <header className="textbook-overlay-head">
        <span>{title ?? "Textbook"}</span>
        <button onClick={onToggle} aria-label="Minimize textbook">
          Minimize
        </button>
      </header>
      <div className="textbook-overlay-body">
        <iframe
          className="textbook-overlay-frame"
          src={src}
          title={title ?? "Textbook"}
        />
      </div>
    </section>
  );
}

function DocIcon() {
  return (
    <svg
      className="textbook-doc-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M8 3h7l4 4v14a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M15 3v4h4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M9.5 12h5M9.5 15.5h5M9.5 19h3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
