from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from .epic import Claim, ClaimDecision, EpicGate, EvidenceRef


EVIDENCE_RANGE = "EPIC_EVIDENCE_MAP!A2:N"
CLAIM_RANGE = "EPIC_CLAIM_GATE!A2:K"


def evidence_from_rows(rows: Iterable[list[Any]]) -> list[EvidenceRef]:
    out: list[EvidenceRef] = []
    for row in rows:
        if not row or not str(row[0]).strip():
            continue
        vals = list(row) + [None] * (14 - len(row))
        out.append(
            EvidenceRef(
                evidence_id=str(vals[0]),
                subject=str(vals[1]),
                predicate=str(vals[2]),
                value=vals[3],
                source=str(vals[4]),
                observed=bool(vals[6]),
                receipt=(str(vals[7]) if vals[7] else None),
                executor=(str(vals[8]) if vals[8] else None),
                router=(str(vals[9]) if vals[9] else None),
                validator=(str(vals[10]) if vals[10] else None),
                lineage_parent=(str(vals[11]) if vals[11] else None),
            )
        )
    return out


def claim_from_row(row: list[Any]) -> Claim:
    vals = list(row) + [None] * (11 - len(row))
    required = tuple(x.strip() for x in str(vals[4] or "").split(";") if x.strip())
    return Claim(
        claim_id=str(vals[0]),
        subject=str(vals[1]),
        predicate=str(vals[2]),
        expected=vals[3],
        required_evidence_ids=required,
        requires_observation=bool(vals[5]),
        requires_receipt=bool(vals[6]),
        asserted_executor=(str(vals[7]) if vals[7] else None),
    )


def evaluate_workbook_claims(
    evidence_rows: Iterable[list[Any]],
    claim_rows: Iterable[list[Any]],
) -> list[dict[str, Any]]:
    evidence = evidence_from_rows(evidence_rows)
    gate = EpicGate(evidence)
    decisions: list[dict[str, Any]] = []
    for row in claim_rows:
        if not row or not str(row[0]).strip():
            continue
        claim = claim_from_row(row)
        decision: ClaimDecision = gate.decide(claim)
        decisions.append(asdict(decision))
    return decisions


def assert_no_execution_authority() -> dict[str, bool]:
    """Machine-readable EPIC boundary declaration.

    Workbook integration may ingest evidence and write claim decisions only.
    It cannot invoke node capabilities, assign authority, mutate runtime state,
    or promote execution state.
    """
    return {
        "runtime_mutation": False,
        "authority_assignment": False,
        "executor_selection": False,
        "node_skill_invocation": False,
        "execution_state_promotion": False,
        "evidence_ingest": True,
        "claim_decision_emit": True,
    }
