#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PRIMARY_RELATIONS = {
    "DEFINITION_OF",
    "SPECIALISES",
    "GENERALISES",
    "LOWERS_TO",
    "EXECUTES_AS",
    "OBSERVED_AS",
    "PROVEN_BY",
}


@dataclass(frozen=True, slots=True)
class DefinitionObject:
    identity: str
    defines: str
    definition_class: str
    value: Any
    relations: tuple[tuple[str, str], ...] = ()
    provenance: tuple[str, ...] = ()
    executable_routes: tuple[str, ...] = ()


class DefinitionGraph:
    """Primary IL-LLM definition substrate.

    Definitions are themselves addressable objects. A definition may therefore
    be the subject of another definition (`DEFINITION_OF`) without relying on
    memory or conversational context to reconstruct its semantics.

    Context and memory are intentionally absent from this core. They are
    secondary traversal/projection layers over the definition graph.
    """

    def __init__(self, *, max_definitions: int = 500_000, max_depth: int = 128) -> None:
        self.max_definitions = max_definitions
        self.max_depth = max_depth
        self.objects: dict[str, DefinitionObject] = {}
        self.definitions_of: dict[str, set[str]] = {}
        self.relations_out: dict[str, list[tuple[str, str]]] = {}

    def register(self, obj: DefinitionObject) -> None:
        if obj.identity in self.objects:
            self._drop(obj.identity)
        elif len(self.objects) >= self.max_definitions:
            raise RuntimeError("definition graph bound exceeded")
        for relation, target in obj.relations:
            if relation not in PRIMARY_RELATIONS:
                raise ValueError(f"unsupported primary relation: {relation}")
            if not target:
                raise ValueError("definition relation target required")
        self.objects[obj.identity] = obj
        self.definitions_of.setdefault(obj.defines, set()).add(obj.identity)
        self.relations_out[obj.identity] = list(obj.relations)

    def _drop(self, identity: str) -> None:
        old = self.objects.get(identity)
        if old is None:
            return
        bucket = self.definitions_of.get(old.defines)
        if bucket is not None:
            bucket.discard(identity)
            if not bucket:
                self.definitions_of.pop(old.defines, None)
        self.relations_out.pop(identity, None)

    def direct_definitions(self, subject: str) -> list[DefinitionObject]:
        return [self.objects[i] for i in sorted(self.definitions_of.get(subject, set()))]

    def definition_chain(self, subject: str) -> dict[str, Any]:
        """Traverse definition-of-definition recursively with explicit bounds."""
        levels: list[list[dict[str, Any]]] = []
        frontier = [subject]
        seen_subjects: set[str] = set()
        depth = 0
        while frontier:
            if depth >= self.max_depth:
                return {
                    "status": "BOUNDED",
                    "subject": subject,
                    "depth": depth,
                    "levels": levels,
                    "reason": "max_definition_depth_reached",
                }
            next_frontier: list[str] = []
            level: list[dict[str, Any]] = []
            for current in frontier:
                if current in seen_subjects:
                    continue
                seen_subjects.add(current)
                for definition in self.direct_definitions(current):
                    level.append({
                        "identity": definition.identity,
                        "defines": definition.defines,
                        "definitionClass": definition.definition_class,
                        "value": definition.value,
                        "relations": list(definition.relations),
                        "provenance": list(definition.provenance),
                        "executableRoutes": list(definition.executable_routes),
                    })
                    # The definition object itself may be defined by a higher-order
                    # definition. That is the core recursive operation.
                    next_frontier.append(definition.identity)
            if level:
                levels.append(level)
            frontier = next_frontier
            depth += 1
        return {
            "status": "RESOLVED",
            "subject": subject,
            "depth": len(levels),
            "levels": levels,
            "claimBoundary": "The chain reports registered machine definitions and higher-order definitions. It does not infer missing semantics from memory or context.",
        }

    def lowerings(self, definition_id: str) -> list[dict[str, str]]:
        if definition_id not in self.objects:
            raise KeyError(definition_id)
        return [
            {"relation": relation, "target": target}
            for relation, target in self.relations_out.get(definition_id, [])
            if relation in {"LOWERS_TO", "EXECUTES_AS"}
        ]
