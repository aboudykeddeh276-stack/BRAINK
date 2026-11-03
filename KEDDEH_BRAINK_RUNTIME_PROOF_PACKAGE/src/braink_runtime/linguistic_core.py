"""Linguistic core: deterministic natural-language to intent mapping.

The linguistic core is the only component permitted to interpret free text. All
downstream components consume the structured intent it emits, never raw text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

__all__ = [
    "LexiconVersion",
    "LinguisticCore",
    "LEXICON_V1",
    "MAX_INPUT_LENGTH",
    "MAX_TOKEN_LENGTH",
]

MAX_INPUT_LENGTH = 4096
MAX_TOKEN_LENGTH = 128

_PUNCTUATION_RE = re.compile(r"[^\w\s-]", re.UNICODE)
_UNDERSCORE_RE = re.compile(r"_+")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LexiconVersion:
    """An immutable, versioned term -> intent mapping."""

    version: str
    terms: Dict[str, str] = field(default_factory=dict)

    def lookup(self, token: str) -> str:
        return self.terms.get(token, "")

    def known_terms(self) -> List[str]:
        return sorted(self.terms)


LEXICON_V1 = LexiconVersion(
    version="lexicon-1.0.0",
    terms={
        "run": "EXECUTE",
        "execute": "EXECUTE",
        "start": "EXECUTE",
        "stop": "HALT",
        "halt": "HALT",
        "kill": "HALT",
        "verify": "VERIFY",
        "check": "VERIFY",
        "validate": "VERIFY",
        "status": "STATUS",
        "state": "STATUS",
        "restart": "RESTART",
        "reboot": "RESTART",
        "recover": "RESTART",
    },
)


class LinguisticCore:
    """Deterministic text normaliser, tokeniser and intent mapper."""

    def __init__(self, lexicon: LexiconVersion = LEXICON_V1) -> None:
        self.lexicon = lexicon

    # -- guards ---------------------------------------------------------
    @staticmethod
    def _guard_input(text: str) -> str:
        if text is None:
            raise ValueError("input text must not be None")
        if not isinstance(text, str):
            raise ValueError("input text must be a string")
        if text.strip() == "":
            raise ValueError("input text must not be empty")
        if len(text) > MAX_INPUT_LENGTH:
            raise ValueError(
                "input text exceeds maximum length of %d characters" % MAX_INPUT_LENGTH
            )
        return text

    # -- primitives -----------------------------------------------------
    def normalize(self, text: str) -> str:
        """Lowercase, strip, collapse whitespace, drop punctuation but hyphens."""
        text = self._guard_input(text)
        lowered = text.lower().strip()
        no_underscores = _UNDERSCORE_RE.sub(" ", lowered)
        depunctuated = _PUNCTUATION_RE.sub(" ", no_underscores)
        return _WHITESPACE_RE.sub(" ", depunctuated).strip()

    def tokenize(self, text: str) -> List[str]:
        """Normalize then split on whitespace."""
        normalized = self.normalize(text)
        if not normalized:
            return []
        return [t for t in normalized.split(" ") if t]

    def validate_token(self, token: str) -> bool:
        """A token is valid when non-empty, whitespace-free and <=128 chars."""
        if token is None or not isinstance(token, str):
            return False
        if token == "":
            return False
        if _WHITESPACE_RE.search(token):
            return False
        return len(token) <= MAX_TOKEN_LENGTH

    # -- intent ---------------------------------------------------------
    def map_intent(self, text: str) -> Dict[str, object]:
        """Map free text to a single best intent.

        Returns a dict with ``intent``, ``tokens``, ``confidence`` and the
        supporting ``matched`` token list plus the lexicon version used.
        """
        tokens = self.tokenize(text)
        matches = [(t, self.lexicon.lookup(t)) for t in tokens]
        hits = [(t, i) for t, i in matches if i]
        if not hits:
            return {
                "intent": "UNKNOWN",
                "tokens": tokens,
                "confidence": 0.0,
                "matched": [],
                "lexicon_version": self.lexicon.version,
            }
        intent = hits[0][1]
        same_intent = [t for t, i in hits if i == intent]
        confidence = round(len(hits) / float(len(tokens)), 4) if tokens else 0.0
        return {
            "intent": intent,
            "tokens": tokens,
            "confidence": confidence,
            "matched": same_intent,
            "lexicon_version": self.lexicon.version,
        }

    def handle_ambiguity(self, tokens: List[str]) -> Dict[str, object]:
        """Score every candidate intent present in ``tokens``."""
        if tokens is None:
            raise ValueError("tokens must not be None")
        if not isinstance(tokens, (list, tuple)):
            raise ValueError("tokens must be a list")
        valid = [t for t in tokens if self.validate_token(t)]
        scores: Dict[str, float] = {}
        for token in valid:
            intent = self.lexicon.lookup(token.lower())
            if intent:
                scores[intent] = scores.get(intent, 0.0) + 1.0
        total = sum(scores.values())
        normalized = (
            {k: round(v / total, 4) for k, v in scores.items()} if total else {}
        )
        ranked = sorted(normalized.items(), key=lambda kv: (-kv[1], kv[0]))
        return {
            "candidates": normalized,
            "ranked": [k for k, _ in ranked],
            "ambiguous": len(normalized) > 1,
            "resolved": ranked[0][0] if ranked else "UNKNOWN",
            "lexicon_version": self.lexicon.version,
        }

    def lexicon_version(self) -> str:
        return self.lexicon.version
