#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EquivalentForm:
    identity: str
    form: str
    cost: float
    proof_status: str
    executable_route: str | None = None


class EquivalenceStore:
    """Bounded equivalence classes for alternate IL-LLM representations.

    This borrows the non-destructive idea from e-graphs: retain alternatives and
    extract by a declared cost policy. It deliberately does not infer semantic
    equivalence; callers must register that relation with evidence/proof status.
    """

    def __init__(self, *, max_classes: int = 50_000, max_forms_per_class: int = 128) -> None:
        self.max_classes = max_classes
        self.max_forms_per_class = max_forms_per_class
        self.classes: dict[str, dict[str, EquivalentForm]] = {}

    def register(self, class_id: str, form: EquivalentForm) -> None:
        if class_id not in self.classes and len(self.classes) >= self.max_classes:
            raise RuntimeError("equivalence class bound exceeded")
        bucket = self.classes.setdefault(class_id, {})
        if form.identity not in bucket and len(bucket) >= self.max_forms_per_class:
            raise RuntimeError("equivalence form bound exceeded")
        if form.cost < 0:
            raise ValueError("equivalence extraction cost must be non-negative")
        bucket[form.identity] = form

    def extract(
        self,
        class_id: str,
        *,
        require_execution: bool = False,
        allowed_proof_status: set[str] | None = None,
    ) -> dict[str, Any]:
        allowed = allowed_proof_status or {"VERIFIED", "MODEL_LOCAL", "DEFINED"}
        forms = [
            form for form in self.classes.get(class_id, {}).values()
            if form.proof_status in allowed and (not require_execution or form.executable_route)
        ]
        forms.sort(key=lambda form: (form.cost, form.identity, form.form))
        if not forms:
            return {"found": False, "classId": class_id}
        selected = forms[0]
        return {
            "found": True,
            "classId": class_id,
            "selected": {
                "identity": selected.identity,
                "form": selected.form,
                "cost": selected.cost,
                "proofStatus": selected.proof_status,
                "executableRoute": selected.executable_route,
            },
            "alternates": [
                {
                    "identity": item.identity,
                    "form": item.form,
                    "cost": item.cost,
                    "proofStatus": item.proof_status,
                    "executableRoute": item.executable_route,
                }
                for item in forms[1:]
            ],
            "claimBoundary": "Registered forms are treated as equivalent only within the supplied class/evidence boundary. Extraction optimizes declared cost; it does not establish mathematical truth.",
        }
