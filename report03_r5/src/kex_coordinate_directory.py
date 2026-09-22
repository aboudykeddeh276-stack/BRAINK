#!/usr/bin/env python3
"""Distributed-state contract for KEX coordinates over the ToT safety kernel.

Authority-changing directory mutations are committed through ToTSafetyKernel.
Manifestation observations are deliberately separate: observations can change
without changing KEX identity or accepted authority state.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, os
from tot_safety_kernel import ToTSafetyKernel, DEFAULT_QUORUM, h

SCHEMA = "keddeh.kex-coordinate-directory.v1"
DIRECTORY_ID = "KEX://DIRECTORY/COORDINATES/DOMAIN-FABRIC/V1"


def canonical(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class CoordinateDirectory:
    def __init__(self, *, kernel: ToTSafetyKernel, state_path: str | Path | None = None):
        self.kernel = kernel
        self.state_path = Path(state_path) if state_path else None
        self.records: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, list[dict[str, Any]]] = {}
        self.applied_commit_index = 0
        if self.state_path and self.state_path.exists():
            self._load()
        self.replay_committed()

    def _body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "directory_id": DIRECTORY_ID,
            "authority_source": self.kernel.snapshot()["kernel_id"],
            "applied_commit_index": self.applied_commit_index,
            "accepted_state_root": self.kernel.committed_root,
            "records": self.records,
            "observations": self.observations,
        }

    def snapshot(self) -> dict[str, Any]:
        body = self._body(); body["directory_root"] = h(body); return body

    def _persist(self) -> None:
        if not self.state_path: return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp=self.state_path.with_suffix(self.state_path.suffix+".tmp")
        tmp.write_text(json.dumps(self.snapshot(),indent=2,sort_keys=True)+"\n")
        os.replace(tmp,self.state_path)

    def _load(self) -> None:
        data=json.loads(self.state_path.read_text()); root=data.pop("directory_root",None)
        if root!=h(data): raise RuntimeError("DIRECTORY_ROOT_MISMATCH")
        self.records=dict(data.get("records",{})); self.observations=dict(data.get("observations",{})); self.applied_commit_index=int(data.get("applied_commit_index",0))

    def replay_committed(self) -> None:
        # Accepted authority state comes exclusively from committed ToT log entries.
        records: dict[str,dict[str,Any]] = {}
        for entry in self.kernel.log:
            op=entry["operation"]; p=entry["payload"]
            if op=="COORDINATE_DEFINE":
                coord=p["coordinate"]
                if coord in records: raise RuntimeError("REPLAY_DUPLICATE_COORDINATE")
                records[coord]={
                    "coordinate":coord,"kind":p["kind"],"authority_epoch":entry["term"],
                    "defined_at_commit":entry["index"],"metadata":p.get("metadata",{}),
                    "desired":p.get("desired",{}),"accepted_entry_root":entry["entry_root"],
                }
            elif op=="COORDINATE_DESIRED_SET":
                coord=p["coordinate"]
                if coord not in records: raise RuntimeError("REPLAY_UNKNOWN_COORDINATE")
                records[coord]["desired"]=p["desired"]
                records[coord]["authority_epoch"]=entry["term"]
                records[coord]["accepted_entry_root"]=entry["entry_root"]
                records[coord]["desired_commit"]=entry["index"]
            elif op=="COORDINATE_METADATA_PATCH":
                coord=p["coordinate"]
                if coord not in records: raise RuntimeError("REPLAY_UNKNOWN_COORDINATE")
                records[coord].setdefault("metadata",{}).update(p["patch"])
                records[coord]["authority_epoch"]=entry["term"]
                records[coord]["accepted_entry_root"]=entry["entry_root"]
        self.records=records
        self.applied_commit_index=self.kernel.commit_index
        self._persist()

    def define(self, coordinate: str, *, kind: str, desired: dict[str,Any] | None=None, metadata: dict[str,Any] | None=None, voters=DEFAULT_QUORUM) -> dict[str,Any]:
        if coordinate in self.records: raise ValueError("COORDINATE_ALREADY_DEFINED")
        out=self.kernel.transition("COORDINATE_DEFINE", {"coordinate":coordinate,"kind":kind,"desired":desired or {},"metadata":metadata or {}}, voters)
        self.replay_committed()
        return {"state":"COORDINATE_DEFINED_COMMITTED","coordinate":coordinate,"commit":out,"record":self.records[coordinate]}

    def set_desired(self, coordinate: str, desired: dict[str,Any], *, voters=DEFAULT_QUORUM) -> dict[str,Any]:
        if coordinate not in self.records: raise ValueError("UNKNOWN_COORDINATE")
        out=self.kernel.transition("COORDINATE_DESIRED_SET", {"coordinate":coordinate,"desired":desired}, voters)
        self.replay_committed()
        return {"state":"DESIRED_STATE_COMMITTED","coordinate":coordinate,"commit":out,"record":self.records[coordinate]}

    def observe_manifestation(self, coordinate: str, observation: dict[str,Any]) -> dict[str,Any]:
        if coordinate not in self.records: raise ValueError("UNKNOWN_COORDINATE")
        # Observation cannot mutate accepted authority state.
        obs=dict(observation)
        obs["observation_root"]=h({"coordinate":coordinate,"observation":observation})
        self.observations.setdefault(coordinate,[]).append(obs)
        self._persist()
        return {"state":"MANIFESTATION_OBSERVATION_RECORDED_NON_AUTHORITY","coordinate":coordinate,"observation":obs,"accepted_state_root":self.kernel.committed_root}

    def resolve(self, coordinate: str) -> dict[str,Any]:
        if coordinate not in self.records: return {"state":"NOT_FOUND","coordinate":coordinate}
        return {
            "state":"RESOLVED_ACCEPTED_COORDINATE",
            "record":self.records[coordinate],
            "manifestation_observations":list(self.observations.get(coordinate,[])),
            "accepted_state_root":self.kernel.committed_root,
            "commit_index":self.kernel.commit_index,
        }