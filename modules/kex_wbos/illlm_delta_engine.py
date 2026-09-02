#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True, slots=True, order=True)
class Fact:
    predicate: str
    subject: str
    object: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.predicate, self.subject, self.object)


@dataclass(frozen=True, slots=True)
class UnaryRule:
    name: str
    input_predicate: str
    output_predicate: str
    transform: Callable[[Fact], Iterable[Fact]]


class DeltaEngine:
    """Bounded semi-naive fact propagation for resident IL-LLM state.

    Only newly inserted facts are evaluated in each round. Existing facts are
    not rescanned, so repeated warm updates scale with the delta and its derived
    consequences rather than the full resident fact set.
    """

    def __init__(self, *, max_rounds: int = 64, max_facts: int = 250_000) -> None:
        if max_rounds <= 0 or max_facts <= 0:
            raise ValueError("positive bounds required")
        self.max_rounds = max_rounds
        self.max_facts = max_facts
        self.facts: set[Fact] = set()
        self.by_predicate: dict[str, set[Fact]] = {}
        self.rules: list[UnaryRule] = []
        self.generation = 0
        self.last_delta_count = 0
        self.last_derived_count = 0
        self.total_rule_evaluations = 0

    def add_rule(self, rule: UnaryRule) -> None:
        self.rules.append(rule)

    def insert(self, facts: Iterable[Fact]) -> dict[str, Any]:
        initial = {fact for fact in facts if fact not in self.facts}
        if not initial:
            return self._receipt(0, 0, 0, 0)
        if len(self.facts) + len(initial) > self.max_facts:
            raise RuntimeError("IL-LLM fact bound exceeded")

        frontier = initial
        all_new: set[Fact] = set()
        rounds = 0
        rule_evaluations = 0
        while frontier:
            rounds += 1
            if rounds > self.max_rounds:
                raise RuntimeError("IL-LLM delta round bound exceeded")
            for fact in frontier:
                self._store(fact)
            all_new.update(frontier)

            next_frontier: set[Fact] = set()
            for rule in self.rules:
                matching = [fact for fact in frontier if fact.predicate == rule.input_predicate]
                rule_evaluations += len(matching)
                for fact in matching:
                    for derived in rule.transform(fact):
                        if derived not in self.facts and derived not in next_frontier:
                            if len(self.facts) + len(next_frontier) >= self.max_facts:
                                raise RuntimeError("IL-LLM fact bound exceeded")
                            next_frontier.add(derived)
            frontier = next_frontier

        self.generation += 1
        self.last_delta_count = len(initial)
        self.last_derived_count = len(all_new) - len(initial)
        self.total_rule_evaluations += rule_evaluations
        return self._receipt(len(initial), self.last_derived_count, rounds, rule_evaluations)

    def _store(self, fact: Fact) -> None:
        self.facts.add(fact)
        self.by_predicate.setdefault(fact.predicate, set()).add(fact)

    def query(self, predicate: str, *, subject: str | None = None, object: str | None = None) -> list[Fact]:
        rows = self.by_predicate.get(predicate, set())
        return sorted(
            fact for fact in rows
            if (subject is None or fact.subject == subject)
            and (object is None or fact.object == object)
        )

    def graph_hash(self) -> str:
        payload = [fact.as_tuple() for fact in sorted(self.facts)]
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _receipt(self, inserted: int, derived: int, rounds: int, evaluations: int) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "inserted": inserted,
            "derived": derived,
            "rounds": rounds,
            "ruleEvaluations": evaluations,
            "residentFactCount": len(self.facts),
            "graphHash": self.graph_hash(),
            "claimBoundary": "Semi-naive propagation reduces repeated rule evaluation for insert-only deltas. It is not a distributed consistency or general Datalog completeness claim.",
        }


def default_kex_rules() -> list[UnaryRule]:
    def contextualise(fact: Fact) -> Iterable[Fact]:
        yield Fact("CONTEXT_REACHABLE", fact.subject, fact.object)

    def executable(fact: Fact) -> Iterable[Fact]:
        yield Fact("MACHINE_REACHABLE", fact.subject, fact.object)

    def prove(fact: Fact) -> Iterable[Fact]:
        yield Fact("PROOF_REQUIRED", fact.subject, fact.object)

    return [
        UnaryRule("contextual_relation", "KEX_RELATION", "CONTEXT_REACHABLE", contextualise),
        UnaryRule("execution_relation", "EXECUTION_ROUTE", "MACHINE_REACHABLE", executable),
        UnaryRule("execution_requires_proof", "MACHINE_REACHABLE", "PROOF_REQUIRED", prove),
    ]
