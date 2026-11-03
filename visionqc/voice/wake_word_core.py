from __future__ import annotations

from dataclasses import dataclass
import re
import time


@dataclass(slots=True)
class WakeWordResult:
    activated: bool = False
    question: str = ""
    heard_text: str = ""


class WakeWordMatcher:
    """Deterministic local wake-word state machine."""

    def __init__(self, wake_word: str = "Vision", conversation_timeout: float = 30.0) -> None:
        self.wake_word = wake_word.strip() or "Vision"
        # Windows recognizers may transcribe the English wake word in Persian script.
        self.wake_aliases = tuple(dict.fromkeys((self.wake_word, "ویژن", "ويژن", "vision qc")))
        self.conversation_timeout = max(5.0, float(conversation_timeout))
        self._armed_until = 0.0

    @property
    def armed(self) -> bool:
        return time.monotonic() < self._armed_until

    def reset(self) -> None:
        self._armed_until = 0.0

    def feed(self, text: str, *, now: float | None = None) -> WakeWordResult:
        heard = " ".join((text or "").split()).strip()
        if not heard:
            return WakeWordResult(heard_text="")
        clock = time.monotonic() if now is None else float(now)
        armed = clock < self._armed_until
        match = None
        for alias in self.wake_aliases:
            escaped = re.escape(alias)
            candidate = re.search(rf"(?<!\w){escaped}(?!\w)", heard, flags=re.IGNORECASE)
            if candidate and (match is None or candidate.start() < match.start()):
                match = candidate
        if match:
            remainder = heard[match.end():].strip(" ,.!?:;-\t،؟")
            self._armed_until = clock + self.conversation_timeout
            return WakeWordResult(activated=True, question=remainder, heard_text=heard)
        if armed:
            self._armed_until = clock + self.conversation_timeout
            return WakeWordResult(activated=True, question=heard, heard_text=heard)
        return WakeWordResult(activated=False, heard_text=heard)
