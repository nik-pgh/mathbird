"""Sentence boundary detection for the AiBoard extractor pipeline.

The agent's streamed text segments are appended to a buffer; this module
finds complete sentences in the buffer and returns them along with whatever
trailing partial sentence is left for the next call.

Boundary rules (intentionally conservative — under-segmenting is fine; the
extractor handles a two-sentence chunk just as well; over-segmenting on
"Dr." or "0.5" would produce malformed input):

- A terminator (``.``, ``?``, ``!``) followed by whitespace and an
  uppercase letter is a sentence boundary.
- A newline always flushes whatever is buffered up to it as a sentence
  (the LLM emits these between turns or paragraphs).
- If the buffer exceeds ``MAX_BUFFER_LEN`` chars without any boundary,
  flush the whole thing — better to send a long chunk than buffer
  indefinitely.
"""

from __future__ import annotations

import re

MAX_BUFFER_LEN = 200

# Matches a sentence terminator (. ? !) followed by one or more spaces
# and an uppercase letter. The lookahead keeps the uppercase letter for
# the next sentence.
_BOUNDARY_RE = re.compile(r"([.?!])\s+(?=[A-Z])")

# Matches a sentence terminator (. ? !) followed by whitespace only until
# end of string — the sentence is complete even with no following sentence.
_TRAILING_RE = re.compile(r"([.?!])\s*$")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Pull complete sentences off the front of ``buffer``.

    Returns ``(sentences, remainder)``: a list of sentences (each stripped
    of trailing whitespace, terminator preserved) and the leftover buffer
    string for the caller to prepend to the next segment.
    """
    sentences: list[str] = []
    pos = 0

    while pos < len(buffer):
        # Newline always flushes.
        nl = buffer.find("\n", pos)
        if nl != -1:
            chunk = buffer[pos:nl].rstrip()
            if chunk:
                sentences.append(chunk)
            pos = nl + 1
            continue

        # Terminator + whitespace + uppercase boundary?
        match = _BOUNDARY_RE.search(buffer, pos)
        if match is None:
            # No mid-string boundary. Check if the buffer ends with a
            # terminator (+ optional trailing whitespace) — that means the
            # final sentence is complete.
            trailing = _TRAILING_RE.search(buffer, pos)
            if trailing is not None:
                chunk = buffer[pos : trailing.end(1) + 1].rstrip()
                if chunk:
                    sentences.append(chunk)
                pos = len(buffer)
            break  # rest is partial (or we just consumed everything)
        end = match.end()  # after the whitespace, at the uppercase letter
        # The sentence includes everything up through the terminator.
        chunk = buffer[pos : match.end(1) + 1].rstrip()
        if chunk:
            sentences.append(chunk)
        pos = end

    remainder = buffer[pos:]

    # Safety valve: if no sentence was found and the buffer is huge,
    # flush it whole.
    if not sentences and len(remainder) >= MAX_BUFFER_LEN:
        return ([remainder], "")

    return (sentences, remainder)
