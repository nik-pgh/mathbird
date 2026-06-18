import { useEffect, useMemo, useRef } from "react";
import DOMPurify from "dompurify";
import {
  useLocalParticipant,
  useTrackTranscription,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { renderMathTextToHtml } from "../lib/mathText";
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
  const micPublication = localParticipant.getTrackPublication(
    Track.Source.Microphone,
  );

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

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  if (lines.length === 0) {
    return (
      <div className="transcript empty">
        <p>Speak naturally — your conversation appears here.</p>
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
  const animated = useTypewriter(
    line.text,
    line.role === "user" ? 80 : 45,
  );
  const isCaughtUp = animated.length >= line.text.length;
  const isInterim = !line.final || !isCaughtUp;
  const isUser = line.role === "user";
  const tutorHtml = useMemo(() => {
    if (isUser) return "";
    return DOMPurify.sanitize(renderMathTextToHtml(animated, { lineBreaks: "collapse" }), {
      USE_PROFILES: { html: true, mathMl: true, svg: true },
    });
  }, [animated, isUser]);

  return (
    <div className="msg">
      <div className="row">
        <div className={`avatar ${isUser ? "you" : "tutor"}`}>
          {isUser ? "Y" : "M"}
        </div>
        <div className="body">
          <div className="who">{isUser ? "You" : "Tutor"}</div>
          <div className={isInterim ? "interim" : ""}>
            {isUser ? (
              animated
            ) : (
              <span dangerouslySetInnerHTML={{ __html: tutorHtml }} />
            )}
            {isInterim && <span className="caret" />}
          </div>
        </div>
      </div>
    </div>
  );
}
