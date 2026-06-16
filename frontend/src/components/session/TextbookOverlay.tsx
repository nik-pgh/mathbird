import { documentFileUrl } from "../../lib/api";

interface Props {
  docId: string | null;
  title: string | null;
  mode: "large" | "small";
  onToggle: () => void;
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
        className="textbook-overlay textbook-overlay-small"
        onClick={onToggle}
        aria-label="Open textbook"
        title={title ?? "Textbook"}
      >
        <span>Textbook</span>
        <strong>{title ?? "Source"}</strong>
      </button>
    );
  }

  const src = `${documentFileUrl(docId)}#toolbar=0&navpanes=0`;
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
      <iframe
        className="textbook-overlay-frame"
        src={src}
        style={{ width: "100%", height: "100%", border: 0 }}
        title={title ?? "Textbook"}
      />
    </section>
  );
}
