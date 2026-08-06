#!/usr/bin/env python3
"""Validate a Keddeh Logical Engineering Contract using Python stdlib only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ID_PATTERNS = {
    "contract": re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$"),
    "requirement": re.compile(r"^REQ-[A-Z0-9-]+$"),
    "invariant": re.compile(r"^INV-[A-Z0-9-]+$"),
    "step": re.compile(r"^STEP-[A-Z0-9-]+$"),
    "message": re.compile(r"^MSG-[A-Z0-9-]+$"),
    "transition": re.compile(r"^TR-[A-Z0-9-]+$"),
}

NORMATIVE = re.compile(
    r"\b(?:MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|"
    r"MUST|REQUIRED|SHALL|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b"
)
LOWERCASE_NORMATIVE = re.compile(r"\b(?:must|shall|should|may)\b")
MATURITY = {"E0", "E1", "E2", "E3", "E4", "E5"}
KINDS = {"system", "process", "procedure", "protocol", "implementation", "verification"}
RECEIPT_FIELDS = {
    "artifact",
    "artifact_hash",
    "source_revision",
    "toolchain",
    "environment",
    "timestamp",
    "result",
    "claim_boundary",
}


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def require_object(self, value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.error(path, "expected object")
            return {}
        return value

    def require_list(self, value: Any, path: str, nonempty: bool = False) -> list[Any]:
        if not isinstance(value, list):
            self.error(path, "expected array")
            return []
        if nonempty and not value:
            self.error(path, "array must not be empty")
        return value

    def require_text(self, value: Any, path: str, minimum: int = 1) -> str:
        if not isinstance(value, str):
            self.error(path, "expected string")
            return ""
        if len(value.strip()) < minimum:
            self.error(path, f"text must contain at least {minimum} characters")
        return value

    def required_keys(self, value: dict[str, Any], path: str, keys: set[str]) -> None:
        for key in sorted(keys):
            if key not in value:
                self.error(path, f"missing required field {key!r}")

    def validate(self, document: Any) -> list[str]:
        root = self.require_object(document, "$")
        self.required_keys(
            root,
            "$",
            {
                "contract_version",
                "id",
                "kind",
                "title",
                "purpose",
                "scope",
                "status",
                "maturity",
                "system_of_interest",
                "authority",
                "definitions",
                "requirements",
                "invariants",
                "process",
                "procedure",
                "protocol",
                "verification",
                "evidence",
                "claim_boundary",
            },
        )
        self.validate_identity(root)
        self.validate_system(root)
        self.validate_definitions(root)
        self.validate_requirements(root)
        self.validate_invariants(root)
        self.validate_process(root)
        self.validate_procedure(root)
        self.validate_protocol(root)
        self.validate_verification(root)
        self.validate_evidence(root)
        self.validate_claim_boundary(root)
        return sorted(set(self.errors))

    def validate_identity(self, root: dict[str, Any]) -> None:
        if root.get("contract_version") != "1.0":
            self.error("$.contract_version", "must equal '1.0'")
        identifier = self.require_text(root.get("id"), "$.id", 3)
        if identifier and not ID_PATTERNS["contract"].fullmatch(identifier):
            self.error("$.id", "invalid contract identifier")
        if root.get("kind") not in KINDS:
            self.error("$.kind", f"must be one of {sorted(KINDS)}")
        self.require_text(root.get("title"), "$.title", 8)
        self.require_text(root.get("purpose"), "$.purpose", 20)
        self.require_text(root.get("scope"), "$.scope", 20)
        if root.get("maturity") not in MATURITY:
            self.error("$.maturity", f"must be one of {sorted(MATURITY)}")

    def validate_system(self, root: dict[str, Any]) -> None:
        system = self.require_object(root.get("system_of_interest"), "$.system_of_interest")
        self.required_keys(system, "$.system_of_interest", {"controlled", "external", "trust_boundaries", "excluded"})
        for field in ("controlled", "trust_boundaries", "excluded"):
            self.require_list(system.get(field), f"$.system_of_interest.{field}", nonempty=True)
        authority = self.require_object(root.get("authority"), "$.authority")
        self.required_keys(
            authority,
            "$.authority",
            {"requesters", "decision", "enforcement", "credentials", "delegation", "revocation", "audit"},
        )
        self.require_list(authority.get("requesters"), "$.authority.requesters", nonempty=True)
        self.require_list(authority.get("credentials"), "$.authority.credentials", nonempty=True)
        for field in ("decision", "enforcement", "delegation", "revocation", "audit"):
            self.require_text(authority.get(field), f"$.authority.{field}", 8)
        if authority.get("decision") == "any caller" or authority.get("enforcement") == "any caller":
            self.error("$.authority", "unbounded caller authority is prohibited")

    def validate_definitions(self, root: dict[str, Any]) -> None:
        definitions = self.require_list(root.get("definitions"), "$.definitions", nonempty=True)
        terms: set[str] = set()
        for index, item in enumerate(definitions):
            path = f"$.definitions[{index}]"
            record = self.require_object(item, path)
            self.required_keys(record, path, {"term", "meaning"})
            term = self.require_text(record.get("term"), f"{path}.term", 2)
            self.require_text(record.get("meaning"), f"{path}.meaning", 10)
            if term in terms:
                self.error(f"{path}.term", "duplicate controlled term")
            terms.add(term)

    def validate_requirements(self, root: dict[str, Any]) -> None:
        requirements = self.require_list(root.get("requirements"), "$.requirements", nonempty=True)
        seen: set[str] = set()
        for index, item in enumerate(requirements):
            path = f"$.requirements[{index}]"
            record = self.require_object(item, path)
            self.required_keys(record, path, {"id", "statement", "rationale", "verification", "source"})
            identifier = self.require_text(record.get("id"), f"{path}.id", 5)
            if identifier and not ID_PATTERNS["requirement"].fullmatch(identifier):
                self.error(f"{path}.id", "invalid requirement identifier")
            if identifier in seen:
                self.error(f"{path}.id", "duplicate requirement identifier")
            seen.add(identifier)
            statement = self.require_text(record.get("statement"), f"{path}.statement", 15)
            obligations = NORMATIVE.findall(statement)
            if len(obligations) != 1:
                self.error(f"{path}.statement", "must contain exactly one uppercase BCP 14 obligation")
            if LOWERCASE_NORMATIVE.search(statement):
                self.error(f"{path}.statement", "lowercase normative keyword is ambiguous")
            self.require_text(record.get("rationale"), f"{path}.rationale", 10)
            self.require_text(record.get("verification"), f"{path}.verification", 5)
            self.require_text(record.get("source"), f"{path}.source", 3)

    def validate_invariants(self, root: dict[str, Any]) -> None:
        invariants = self.require_list(root.get("invariants"), "$.invariants", nonempty=True)
        seen: set[str] = set()
        for index, item in enumerate(invariants):
            path = f"$.invariants[{index}]"
            record = self.require_object(item, path)
            self.required_keys(record, path, {"id", "statement", "enforcement", "failure_action"})
            identifier = self.require_text(record.get("id"), f"{path}.id", 5)
            if identifier and not ID_PATTERNS["invariant"].fullmatch(identifier):
                self.error(f"{path}.id", "invalid invariant identifier")
            if identifier in seen:
                self.error(f"{path}.id", "duplicate invariant identifier")
            seen.add(identifier)
            for field in ("statement", "enforcement", "failure_action"):
                self.require_text(record.get(field), f"{path}.{field}", 10)

    def validate_process(self, root: dict[str, Any]) -> None:
        process = self.require_object(root.get("process"), "$.process")
        self.required_keys(process, "$.process", {"owner", "entry_criteria", "activities", "exit_criteria", "records", "feedback"})
        self.require_text(process.get("owner"), "$.process.owner", 3)
        for field in ("entry_criteria", "activities", "exit_criteria", "records"):
            self.require_list(process.get(field), f"$.process.{field}", nonempty=True)
        self.require_text(process.get("feedback"), "$.process.feedback", 10)

    def validate_procedure(self, root: dict[str, Any]) -> None:
        procedure = self.require_object(root.get("procedure"), "$.procedure")
        self.required_keys(
            procedure,
            "$.procedure",
            {"authorised_actor", "prerequisites", "tools", "steps", "stop_conditions", "rollback", "evidence"},
        )
        self.require_text(procedure.get("authorised_actor"), "$.procedure.authorised_actor", 3)
        for field in ("prerequisites", "tools", "stop_conditions", "rollback", "evidence"):
            self.require_list(procedure.get(field), f"$.procedure.{field}", nonempty=True)
        steps = self.require_list(procedure.get("steps"), "$.procedure.steps", nonempty=True)
        seen: set[str] = set()
        for index, item in enumerate(steps):
            path = f"$.procedure.steps[{index}]"
            step = self.require_object(item, path)
            self.required_keys(step, path, {"id", "actor", "precondition", "action", "expected_observation", "failure_action", "evidence"})
            identifier = self.require_text(step.get("id"), f"{path}.id", 6)
            if identifier and not ID_PATTERNS["step"].fullmatch(identifier):
                self.error(f"{path}.id", "invalid step identifier")
            if identifier in seen:
                self.error(f"{path}.id", "duplicate step identifier")
            seen.add(identifier)
            for field in ("actor", "precondition", "action", "expected_observation", "failure_action", "evidence"):
                self.require_text(step.get(field), f"{path}.{field}", 3)
            if step.get("action") == step.get("expected_observation"):
                self.error(path, "expected observation must be independent of the action")

    def validate_protocol(self, root: dict[str, Any]) -> None:
        protocol = self.require_object(root.get("protocol"), "$.protocol")
        self.required_keys(
            protocol,
            "$.protocol",
            {"participants", "states", "initial_state", "terminal_states", "messages", "transitions", "ordering", "freshness", "idempotency", "timeouts", "retries", "versioning", "security", "failure_semantics"},
        )
        participants = self.require_list(protocol.get("participants"), "$.protocol.participants", nonempty=True)
        states = self.require_list(protocol.get("states"), "$.protocol.states", nonempty=True)
        terminal = self.require_list(protocol.get("terminal_states"), "$.protocol.terminal_states", nonempty=True)
        participant_set = {item for item in participants if isinstance(item, str)}
        state_set = {item for item in states if isinstance(item, str)}
        if len(participant_set) != len(participants):
            self.error("$.protocol.participants", "participants must be unique strings")
        if len(state_set) != len(states):
            self.error("$.protocol.states", "states must be unique strings")
        initial = protocol.get("initial_state")
        if initial not in state_set:
            self.error("$.protocol.initial_state", "initial state is not declared")
        for state in terminal:
            if state not in state_set:
                self.error("$.protocol.terminal_states", f"unknown terminal state {state!r}")

        messages = self.require_list(protocol.get("messages"), "$.protocol.messages", nonempty=True)
        message_ids: set[str] = set()
        for index, item in enumerate(messages):
            path = f"$.protocol.messages[{index}]"
            message = self.require_object(item, path)
            self.required_keys(message, path, {"id", "sender", "receiver", "fields", "encoding", "authentication"})
            identifier = self.require_text(message.get("id"), f"{path}.id", 5)
            if identifier and not ID_PATTERNS["message"].fullmatch(identifier):
                self.error(f"{path}.id", "invalid message identifier")
            if identifier in message_ids:
                self.error(f"{path}.id", "duplicate message identifier")
            message_ids.add(identifier)
            for field in ("sender", "receiver"):
                actor = message.get(field)
                if actor not in participant_set:
                    self.error(f"{path}.{field}", f"unknown participant {actor!r}")
            self.require_list(message.get("fields"), f"{path}.fields", nonempty=True)
            self.require_text(message.get("encoding"), f"{path}.encoding", 8)
            self.require_text(message.get("authentication"), f"{path}.authentication", 8)

        transitions = self.require_list(protocol.get("transitions"), "$.protocol.transitions", nonempty=True)
        transition_ids: set[str] = set()
        incoming = {state: 0 for state in state_set}
        outgoing = {state: 0 for state in state_set}
        for index, item in enumerate(transitions):
            path = f"$.protocol.transitions[{index}]"
            transition = self.require_object(item, path)
            self.required_keys(transition, path, {"id", "from", "trigger", "guard", "actor", "action", "to", "failure", "evidence"})
            identifier = self.require_text(transition.get("id"), f"{path}.id", 4)
            if identifier and not ID_PATTERNS["transition"].fullmatch(identifier):
                self.error(f"{path}.id", "invalid transition identifier")
            if identifier in transition_ids:
                self.error(f"{path}.id", "duplicate transition identifier")
            transition_ids.add(identifier)
            source = transition.get("from")
            target = transition.get("to")
            if source not in state_set:
                self.error(f"{path}.from", f"unknown state {source!r}")
            else:
                outgoing[source] += 1
            if target not in state_set:
                self.error(f"{path}.to", f"unknown state {target!r}")
            else:
                incoming[target] += 1
            trigger = transition.get("trigger")
            if trigger not in message_ids and trigger not in {"TIMEOUT", "FAULT", "LOCAL_ACTION"}:
                self.error(f"{path}.trigger", "trigger is not a declared message or reserved local event")
            actor = transition.get("actor")
            if actor not in participant_set:
                self.error(f"{path}.actor", f"unknown participant {actor!r}")
            for field in ("guard", "action", "failure", "evidence"):
                self.require_text(transition.get(field), f"{path}.{field}", 3)
        if initial in outgoing and outgoing[initial] == 0:
            self.error("$.protocol.initial_state", "initial state has no outgoing transition")
        for state in terminal:
            if state in incoming and incoming[state] == 0:
                self.error("$.protocol.terminal_states", f"terminal state {state!r} is unreachable")
        for field in ("ordering", "freshness", "idempotency", "timeouts", "retries", "versioning", "security", "failure_semantics"):
            self.require_text(protocol.get(field), f"$.protocol.{field}", 10)

    def validate_verification(self, root: dict[str, Any]) -> None:
        verification = self.require_object(root.get("verification"), "$.verification")
        self.required_keys(verification, "$.verification", {"static", "dynamic", "fault_injection", "acceptance", "independence", "traceability"})
        for field in ("static", "dynamic", "fault_injection", "acceptance"):
            self.require_list(verification.get(field), f"$.verification.{field}", nonempty=True)
        self.require_text(verification.get("independence"), "$.verification.independence", 10)
        traceability = self.require_object(verification.get("traceability"), "$.verification.traceability")
        requirement_ids = {
            item.get("id")
            for item in root.get("requirements", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for identifier in sorted(requirement_ids - set(traceability)):
            self.error("$.verification.traceability", f"missing trace for {identifier}")
        for identifier in sorted(set(traceability) - requirement_ids):
            self.error("$.verification.traceability", f"unknown requirement {identifier}")
        for identifier, evidence in traceability.items():
            self.require_list(evidence, f"$.verification.traceability.{identifier}", nonempty=True)

    def validate_evidence(self, root: dict[str, Any]) -> None:
        evidence = self.require_object(root.get("evidence"), "$.evidence")
        self.required_keys(evidence, "$.evidence", {"required_artifacts", "receipt_fields", "retention", "integrity"})
        self.require_list(evidence.get("required_artifacts"), "$.evidence.required_artifacts", nonempty=True)
        fields = self.require_list(evidence.get("receipt_fields"), "$.evidence.receipt_fields", nonempty=True)
        missing = RECEIPT_FIELDS - {field for field in fields if isinstance(field, str)}
        if missing:
            self.error("$.evidence.receipt_fields", f"missing required fields {sorted(missing)}")
        self.require_text(evidence.get("retention"), "$.evidence.retention", 10)
        self.require_text(evidence.get("integrity"), "$.evidence.integrity", 10)

    def validate_claim_boundary(self, root: dict[str, Any]) -> None:
        boundary = self.require_object(root.get("claim_boundary"), "$.claim_boundary")
        self.required_keys(boundary, "$.claim_boundary", {"proven", "not_proven", "next_gates"})
        proven = self.require_list(boundary.get("proven"), "$.claim_boundary.proven", nonempty=True)
        not_proven = self.require_list(boundary.get("not_proven"), "$.claim_boundary.not_proven", nonempty=True)
        self.require_list(boundary.get("next_gates"), "$.claim_boundary.next_gates", nonempty=True)
        overlap = {str(item) for item in proven} & {str(item) for item in not_proven}
        if overlap:
            self.error("$.claim_boundary", f"claims appear in proven and not_proven: {sorted(overlap)}")
        if root.get("maturity") in {"E0", "E1", "E2", "E3"}:
            for index, claim in enumerate(proven):
                if isinstance(claim, str) and re.search(r"\b(?:production|physical deployment|certified|fully deployed)\b", claim, re.IGNORECASE):
                    self.error(f"$.claim_boundary.proven[{index}]", "E0-E3 evidence cannot assert production or physical deployment")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)

    try:
        raw = args.contract.read_bytes()
        document = json.loads(raw)
        errors = Validator().validate(document)
        receipt = {
            "contract": str(args.contract),
            "contract_sha256": sha256(raw).hexdigest(),
            "result": "PASS" if not errors else "FAIL",
            "error_count": len(errors),
            "errors": errors,
        }
    except (OSError, json.JSONDecodeError) as exc:
        receipt = {
            "contract": str(args.contract),
            "result": "FAIL",
            "error_count": 1,
            "errors": [f"validator failure: {exc}"],
        }

    output = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return 0 if receipt["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
