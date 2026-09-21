#!/usr/bin/env python3
"""Declarative Layer-2 reconciler over committed KEX coordinate state."""
from __future__ import annotations
from typing import Any
from dataclasses import dataclass, asdict
import hashlib, json
from kex_coordinate_directory import CoordinateDirectory
from tot_safety_kernel import h

SCHEMA="keddeh.layer2-reconciler.v1"

@dataclass(frozen=True)
class Plan:
    schema: str
    coordinate: str
    accepted_state_root: str
    commit_index: int
    desired_root: str
    observed_root: str
    actions: tuple[dict[str,Any], ...]
    plan_root: str


class Layer2Reconciler:
    def __init__(self, directory: CoordinateDirectory):
        self.directory=directory

    def plan(self, coordinate: str, observed: dict[str,Any] | None=None) -> Plan:
        resolved=self.directory.resolve(coordinate)
        if resolved["state"]!="RESOLVED_ACCEPTED_COORDINATE": raise ValueError("UNKNOWN_COORDINATE")
        desired=resolved["record"].get("desired",{})
        observed=observed or {}
        actions=[]
        # bounded generic derivation: each desired key is reconciled independently.
        for key in sorted(desired):
            if observed.get(key)!=desired[key]:
                actions.append({"action":"SET_OR_MATERIALISE","field":key,"from":observed.get(key),"to":desired[key]})
        for key in sorted(set(observed)-set(desired)):
            if key.startswith("managed_"):
                actions.append({"action":"DETACH_UNDESIRED_MANAGED_FIELD","field":key,"from":observed[key]})
        body={
            "schema":SCHEMA,"coordinate":coordinate,
            "accepted_state_root":resolved["accepted_state_root"],"commit_index":resolved["commit_index"],
            "desired_root":h(desired),"observed_root":h(observed),
        }
        root_body={**body,"actions":actions}
        return Plan(**body,actions=tuple(actions),plan_root=h(root_body))

    def apply(self, plan: Plan, executor) -> dict[str,Any]:
        # Immutable plan / optimistic accepted-state fence.
        if self.directory.kernel.committed_root!=plan.accepted_state_root or self.directory.kernel.commit_index!=plan.commit_index:
            raise RuntimeError("RECONCILE_PLAN_STALE_ACCEPTED_STATE_CHANGED")
        if not plan.actions:
            return {"state":"NOOP_ALREADY_CONVERGED","plan_root":plan.plan_root,"results":[]}
        results=[]
        for action in plan.actions:
            results.append(executor(action))
        return {"state":"PLAN_APPLIED_MANIFESTATION_ACTIONS_ONLY","plan_root":plan.plan_root,"results":results,"accepted_state_root":self.directory.kernel.committed_root}