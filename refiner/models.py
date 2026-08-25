from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    POLISH = "polish"
    TONE = "tone"
    SUMMARIZE = "summarize"


class Tone(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    BUSINESS = "business"
    FRIENDLY = "friendly"


@dataclass
class RefineRequest:
    text: str
    mode: Mode = Mode.POLISH
    tone: Tone | None = None
    context: str | None = None
    style_profile: str | None = None


@dataclass
class RefineResult:
    refined_text: str = ""
    changes: list[dict[str, str]] = field(default_factory=list)
    success: bool = True
    error: str | None = None

    @classmethod
    def failure(cls, error: str) -> "RefineResult":
        return cls(success=False, error=error)
