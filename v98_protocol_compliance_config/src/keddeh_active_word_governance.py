#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ActiveWordState:
    address: str
    word: str
    canonical_identity: str
    resolution_state: str
    context: Dict[str, Any]
    expression: Dict[str, Any]
    sector: str
    service: str
    observer: Dict[str, Any]
    execution_plane: str
    evidence_class: str
    dependencies: Dict[str, List[str]]
    state: str
    lineage: Dict[str, Any]
    allowed_transitions: List[str]
    timestamp: float


class ActiveWordGovernance:
    """Context-preserving active lexicon runtime bound to Active Story and IL-LLM.

    Unknown terms are not terminal errors. They become provisional complete values with
    preserved context, bounded execution, bilateral links and a Mirror Lane resolution
    packet. The runtime continues while the lexical definition is translated.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.policy = read_json(self.root / "config" / "active_word_governance.json")
        self.story = read_json(self.root / "config" / "active_story_lexicon.json")
        self.il_llm = read_json(self.root / "config" / "il_llm_active_story_registry.json")
        self.words = {entry["id"]: entry for entry in self.story["words"]}
        self.instances_dir = self.root / "runtime_volume" / "active_words" / "instances"
        self.ledger_path = self.root / "runtime_volume" / "active_words" / "state_ledger.jsonl"
        self.backlinks_path = self.root / "runtime_volume" / "active_words" / "backlinks.json"
        self.provisional_path = self.root / "runtime_volume" / "active_words" / "provisional_lexicon.json"
        self.mirror_dir = self.root / "runtime_volume" / "workplans" / "active_word_mirror_lane"

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.policy.get("equation") != "A_W=f(W,C,E,S,V,O,L,T)":
            errors.append("invalid_equation")
        if self.il_llm.get("wordModel") != "(- WORD +)":
            errors.append("il_llm_word_model_missing")
        for word_id, word in self.words.items():
            for field in ("term", "definition", "invariants", "variants"):
                if not word.get(field):
                    errors.append(f"{word_id}:missing:{field}")
        return errors

    def _resolve_word(self, word_id: str, context: Dict[str, Any], lineage: Dict[str, Any]) -> Tuple[Dict[str, Any], str, Optional[Dict[str, Any]]]:
        known = self.words.get(word_id)
        if known is not None:
            return known, "TRANSLATED", None

        term = word_id.split("://", 1)[-1].replace("-", "_").upper()
        provisional = {
            "id": word_id,
            "term": term,
            "definition": "Provisional active value whose final source definition is pending bilateral IL-LLM translation.",
            "invariants": [
                "source_expression_preserved",
                "context_preserved",
                "observer_preserved",
                "lineage_preserved",
                "no_global_stop_from_missing_term",
            ],
            "variants": ["untranslated", "provisional", "context_bound"],
            "resolution_state": "UNTRANSLATED",
            "source_context": context,
            "source_lineage": lineage,
        }
        provisional_registry = read_json(self.provisional_path) if self.provisional_path.exists() else {}
        provisional_registry[word_id] = provisional
        write_json(self.provisional_path, provisional_registry)
        self.words[word_id] = provisional

        proposal_seed = {
            "word_id": word_id,
            "context": context,
            "lineage": lineage,
            "required_path": ["ANCHOR", "FACTOR", "TRANSLATE", "VALIDATE", "PRESERVE", "RETURN"],
        }
        proposal_id = "proposal://mirror-lane/" + canonical_hash(proposal_seed)
        proposal = {
            "proposal_id": proposal_id,
            "kind": "UNTRANSLATED_ACTIVE_WORD",
            "word_id": word_id,
            "provisional_definition": provisional["definition"],
            "context": context,
            "lineage": lineage,
            "state": "PROPOSED_UPDATE",
            "required_path": ["MIRRORED", "VALIDATED", "REINTEGRATED"],
            "execution_continues": True,
            "global_stop": False,
            "created_at": time.time(),
        }
        write_json(self.mirror_dir / f"{proposal_id.rsplit('/', 1)[-1]}.json", proposal)
        return provisional, "UNTRANSLATED", proposal

    def instantiate(
        self,
        word_id: str,
        context: Dict[str, Any],
        expression: Dict[str, Any],
        sector: str,
        service: str,
        observer: Dict[str, Any],
        execution_plane: str,
        evidence_class: str,
        dependencies: Dict[str, List[str]],
        state: str,
        lineage: Dict[str, Any],
        allowed_transitions: List[str],
    ) -> Dict[str, Any]:
        if execution_plane not in self.policy["executionPlanes"]:
            return {"promotion_state": "CONTEXT_RESOLUTION_REQUIRED", "global_stop": False, "field": "execution_plane"}
        if evidence_class not in self.policy["evidenceClasses"]:
            return {"promotion_state": "CONTEXT_RESOLUTION_REQUIRED", "global_stop": False, "field": "evidence_class"}
        all_states = set(self.policy["stateMachine"]["primary"] + self.policy["stateMachine"]["boundedFailure"])
        if state not in all_states:
            return {"promotion_state": "CONTEXT_RESOLUTION_REQUIRED", "global_stop": False, "field": "state"}

        word, resolution_state, mirror_proposal = self._resolve_word(word_id, context, lineage)
        timestamp = time.time()
        seed = {
            "word": word_id,
            "context": context,
            "expression": expression,
            "sector": sector,
            "service": service,
            "observer": observer,
            "execution_plane": execution_plane,
            "evidence_class": evidence_class,
            "dependencies": dependencies,
            "state": state,
            "resolution_state": resolution_state,
            "lineage": lineage,
            "timestamp": timestamp,
        }
        instance_id = canonical_hash(seed)
        context_slug = str(context.get("domain", "context")).replace(" ", "-").lower()
        state_obj = ActiveWordState(
            address=f"word://{word_id.split('://',1)[-1]}/{sector.split('://',1)[-1]}/{service.split('://',1)[-1]}/{context_slug}/{state.lower()}/{instance_id}",
            word=word["term"],
            canonical_identity=word_id,
            resolution_state=resolution_state,
            context=context,
            expression=expression,
            sector=sector,
            service=service,
            observer=observer,
            execution_plane=execution_plane,
            evidence_class=evidence_class,
            dependencies=dependencies,
            state=state,
            lineage={
                **lineage,
                "lexical_resolution": resolution_state,
                "mirror_proposal": mirror_proposal["proposal_id"] if mirror_proposal else None,
            },
            allowed_transitions=allowed_transitions,
            timestamp=timestamp,
        )
        payload = asdict(state_obj)
        write_json(self.instances_dir / f"{instance_id}.json", payload)
        append_jsonl(self.ledger_path, payload)

        backlinks = read_json(self.backlinks_path) if self.backlinks_path.exists() else {}
        for address in (word_id, sector, service, str(lineage.get("source", "source://unknown"))):
            backlinks.setdefault(address, [])
            if state_obj.address not in backlinks[address]:
                backlinks[address].append(state_obj.address)
        write_json(self.backlinks_path, backlinks)

        return {
            "promotion_state": "ACTIVE_WORD_INSTANTIATED" if resolution_state == "TRANSLATED" else "ACTIVE_WORD_PROVISIONAL",
            "execution_mode": "NORMAL" if resolution_state == "TRANSLATED" else "BOUNDED_CONTEXT_CONTINUATION",
            "global_stop": False,
            "active_word": payload,
            "source_definition": word["definition"],
            "source_invariants": word["invariants"],
            "mirror_proposal": mirror_proposal,
            "il_llm_transition": self.il_llm["canonicalTransition"],
            "bilateral_readback": state_obj.address in backlinks[word_id] and state_obj.address in backlinks[service],
        }

    def transition(self, address: str, next_state: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        instance_id = address.rsplit("/", 1)[-1]
        path = self.instances_dir / f"{instance_id}.json"
        if not path.exists():
            return {"promotion_state": "CONTEXT_RESOLUTION_REQUIRED", "global_stop": False, "missing_instance": address}
        current = read_json(path)
        if next_state not in current["allowed_transitions"]:
            return {
                "promotion_state": "BOUNDED_STOP",
                "global_stop": False,
                "capability_effect": f"hold only {current['service']} transition",
                "reason": "transition_not_allowed",
            }
        updated = dict(current)
        updated["lineage"] = {
            **current["lineage"],
            "prior_address": current["address"],
            "prior_state": current["state"],
            "transition_evidence": evidence,
        }
        updated["state"] = next_state
        updated["timestamp"] = time.time()
        updated["address"] = current["address"].rsplit("/", 2)[0] + f"/{next_state.lower()}/{canonical_hash(updated)}"
        write_json(path, updated)
        append_jsonl(self.ledger_path, updated)
        return {
            "promotion_state": "STATE_TRANSITIONED",
            "execution_mode": "BOUNDED_CONTEXT_CONTINUATION" if updated.get("resolution_state") == "UNTRANSLATED" else "NORMAL",
            "global_stop": False,
            "active_word": updated,
        }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    runtime = ActiveWordGovernance(Path(args.root))
    errors = runtime.validate()
    result = runtime.instantiate(
        word_id="word://verify",
        context={"domain": "application-deployment", "purpose": "node-side execution", "environment": "k-cloud-mesh"},
        expression={"subject": "k-app-package", "action": "verify", "object": "immutable-manifest"},
        sector="sector://application-deployment",
        service="service://k-cloud-admission",
        observer={"type": "admission-controller", "identity": "service://k-cloud-admission"},
        execution_plane="CONTROL_PLANE",
        evidence_class="RECEIPT_BACKED",
        dependencies={"required": ["manifest-integrity", "policy-resolution"], "optional": ["remote-telemetry"]},
        state="ACTIVE",
        lineage={"source": "canonical-lexicon", "prior_state": "ADMITTED", "next_state": "VERIFIED"},
        allowed_transitions=["OBSERVED", "VERIFIED", "DEGRADED", "DEFERRED"],
    )
    payload = {"registry_valid": not errors, "errors": errors, "result": result}
    if args.emit_receipt:
        write_json(runtime.root / "evidence" / "active_word_governance_receipt.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors and result.get("bilateral_readback") else 1


if __name__ == "__main__":
    raise SystemExit(main())
