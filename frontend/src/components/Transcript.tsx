import { useEffect, useMemo, useRef } from "react";
import {
  useLocalParticipant,
  useTrackTranscription,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useTypewriter } from "../lib/useTypewriter";

type Role = "user" | "agent";

interface Line {
  id: string;
  role: Role;
  text: string;
  final: boolean;
  startedAt: number;
}

export default function Transcript() {
  const { agentTranscriptions } = useVoiceAssistant();
  const { localParticipant } = useLocalParticipant();

  const micPublication = localParticipant.getTrackPublication(Track.Source.Microphone);

  const { segments: userSegments } = useTrackTranscription({
    publication: micPublication,
    source: Track.Source.Microphone,
    participant: localParticipant,
  });

  const lines: Line[] = useMemo(() => {
    const u: Line[] = userSegments.map((s) => ({
      id: `u-${s.id}`,
      role: "user",
      text: s.text,
      final: s.final,
      startedAt: s.firstReceivedTime ?? 0,
    }));
    const a: Line[] = agentTranscriptions.map((s) => ({
      id: `a-${s.id}`,
      role: "agent",
      text: s.text,
      final: s.final,
      startedAt: s.firstReceivedTime ?? 0,
    }));
    return [...u, ...a].sort((x, y) => x.startedAt - y.startedAt);
  }, [userSegments, agentTranscriptions]);

  // Auto-scroll to bottom whenever a new line appears or grows.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  if (lines.length === 0) {
    return (
      <div className="transcript empty">
        <p>대화를 시작하세요. 자막이 여기에 표시됩니다.</p>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="transcript">
      {lines.map((line) => (
        <TranscriptLine key={line.id} line={line} />
      ))}
    </div>
  );
}

function TranscriptLine({ line }: { line: Line }) {
  // User speech is typically already streamed via STT interim results, so the
  // raw text already grows naturally. We still pipe it through the typewriter
  // for visual consistency with the agent side; corrections snap.
  const animated = useTypewriter(line.text, line.role === "user" ? 80 : 45);
  const isCaughtUp = animated.length >= line.text.length;

  return (
    <div className={`bubble ${line.role} ${line.final ? "final" : "interim"}`}>
      <div className="role-label">{line.role === "user" ? "You" : "Agent"}</div>
      <div className="bubble-text">
        {animated}
        {(!line.final || !isCaughtUp) && <span className="caret">▍</span>}
      </div>
    </div>
  );
}
