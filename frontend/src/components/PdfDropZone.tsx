import { useCallback, useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export default function PdfDropZone({ onFiles, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const filterPdfs = (files: FileList | File[]) =>
    Array.from(files).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
    );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const pdfs = filterPdfs(e.dataTransfer.files);
      if (pdfs.length) onFiles(pdfs);
    },
    [disabled, onFiles],
  );

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) onFiles(filterPdfs(e.target.files));
          e.target.value = "";
        }}
      />
      <div className="dropzone-inner">
        <div className="dropzone-arrow">↑</div>
        <p className="dropzone-title">
          {dragging ? "Drop to upload" : "Drop PDFs here or click to choose"}
        </p>
        <p className="dropzone-hint">PDFs are indexed for retrieval during the session.</p>
      </div>
    </div>
  );
}
