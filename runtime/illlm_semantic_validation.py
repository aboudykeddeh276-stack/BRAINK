"""Resident IL-LLM event semantic verification, additive to hash-chain readback.

Architect: A. Keddeh / KS-BRAINK-IL-LLM.

The event ID is derived for every ledger event. V4 mirror events additionally
carry self-contained observer, polygon and receipt state, allowing independent
recomputation of their candidate, lexical, IL-LLM, correlation and admission
roots. This is internal consistency verification, not a signature or an
external provenance anchor. Other ledger event families retain their original
schema and are not falsely interpreted as V4 mirror records.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

V4_LEVEL = "OBSERVER_MIRROR_ONLY"
V4_TYPE = "POLYGON_MIRROR_CANDIDATE"
V4_URI_PREFIX = "braink://learning/v4/browser/"
V4_FORMULA = "O_AS_OBS=1_O⊗S_O(E)"


def _object(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, dict) else None


def semantic_violation(event: Mapping[str, Any], digest: Callable[[Any], str]) -> str | None:
    """Return the first violated identity contract, or None on success.

    ``digest`` is the ledger's own canonical SHA-256 root function, so no new
    canonicalisation convention or historical event format is introduced.
    """
    try:
        expected_event_id = digest({
            "correlation_id": event["correlation_id"],
            "source_uri": event["source_uri"],
            "semantic_type": event["semantic_type"],
            "illlm_root": event["illlm_root"],
        })
        if event.get("event_id") != expected_event_id:
            return "EVENT_ID"

        payload = _object(event.get("payload"))
        state = _object(payload.get("state")) if payload else None
        # A V4-shaped receipt remains V4 even when its identity labels are
        # rewritten and the hash chain is recomputed. This is a narrow marker:
        # unrelated ledger event families keep their original schema.
        # A damaged or deliberately stripped V4 receipt must not make a
        # still-recognisable observer/polygon candidate into a generic event.
        # Use multiple independent V4-specific structural markers; do not
        # classify unrelated generic events from a single common field.
        v4_payload = (
            (state is not None and (
                "v4_receipt" in state
                or all(key in state for key in ("observer", "polygon", "source_sha256"))
            ))
            or (payload is not None and all(
                key in payload for key in ("candidate_hash", "observer_policy_digest")
            ))
        )
        v4 = (event.get("source_level") == V4_LEVEL
              or event.get("semantic_type") == V4_TYPE
              or str(event.get("source_uri", "")).startswith(V4_URI_PREFIX)
              or v4_payload)
        if not v4:
            return None
        if event.get("source_level") != V4_LEVEL:
            return "V4_SOURCE_LEVEL"
        if event.get("semantic_type") != V4_TYPE:
            return "V4_SEMANTIC_TYPE"

        if not state:
            return "V4_STATE"
        observer = _object(state.get("observer"))
        polygon = _object(state.get("polygon"))
        receipt = _object(state.get("v4_receipt"))
        if not observer or not polygon or not receipt:
            return "V4_STATE_COMPONENTS"
        instance = state.get("instance_id")
        source = state.get("source_sha256")
        receipt_id = receipt.get("id")
        if not all(isinstance(v, str) and v for v in (instance, source, receipt_id)):
            return "V4_SOURCE_IDENTITY"
        if (observer.get("wholeIdentity") != "1_BRAINK"
                or observer.get("stateFormula") != V4_FORMULA):
            return "V4_OBSERVER_FORMULA"
        if payload.get("promotion_state") != "NOT_PROMOTED":
            return "V4_PROMOTION"
        if payload.get("candidate_hash") != digest(state):
            return "V4_CANDIDATE_HASH"
        if event.get("source_uri") != V4_URI_PREFIX + instance:
            return "V4_SOURCE_URI"
        expected_correlation = digest({
            "instance_id": instance,
            "v4_receipt_id": receipt_id,
            "source_sha256": source,
        })
        if event.get("correlation_id") != expected_correlation:
            return "V4_CORRELATION_ID"
        expected_lexical = digest({
            "source": "V4", "receipt": receipt,
            "polygon_lexical_context": polygon,
        })
        if event.get("lexical_root") != expected_lexical:
            return "V4_LEXICAL_ROOT"
        expected_illlm = digest({
            "candidate": payload["candidate_hash"],
            "observer": observer,
            "source": source,
            "authority": "MIRROR_ONLY",
        })
        if event.get("illlm_root") != expected_illlm:
            return "V4_ILLLM_ROOT"
        expected_policy = digest({
            "candidate_must_be_mirror_only": True,
            "resident_capability_required": True,
        })
        if payload.get("observer_policy_digest") != expected_policy:
            return "V4_ADMISSION_POLICY"
        seq = payload.get("sequence")
        if type(seq) is not int or seq < 1:
            return "V4_SEQUENCE"
        iteration = polygon.get("iteration")
        if type(iteration) is not int or iteration < 0:
            return "V4_ITERATION"
        if (receipt.get("type") == "POLYGON_100_ITERATION" and "iteration" in receipt
                and receipt["iteration"] != iteration):
            return "V4_RECEIPT_ITERATION"
        return None
    except (KeyError, TypeError, ValueError, OverflowError):
        return "MALFORMED_SEMANTIC_EVENT"
