from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class PredicateResult:
    name: str
    satisfied: bool
    evidence: str

def truth_fraction(results: Iterable[PredicateResult]) -> float:
    xs=list(results)
    return 1.0 if not xs else sum(1 for x in xs if x.satisfied)/len(xs)

def all_required_satisfied(results: Iterable[PredicateResult]) -> bool:
    xs=list(results)
    return bool(xs) and all(x.satisfied for x in xs)
