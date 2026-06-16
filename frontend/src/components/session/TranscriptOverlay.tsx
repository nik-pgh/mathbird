import Transcript from "../Transcript";

interface Props {
  open: boolean;
  onToggle: () => void;
}

export default function TranscriptOverlay({ open, onToggle }: Props) {
  return (
    <section
      className="transcript-overlay"
      aria-label="Transcript"
      hidden={!open}
    >
      <header className="transcript-overlay-head">
        <span>Transcript</span>
        <button onClick={onToggle} aria-label="Hide transcript">
          Hide
        </button>
      </header>
      <Transcript />
    </section>
  );
}
