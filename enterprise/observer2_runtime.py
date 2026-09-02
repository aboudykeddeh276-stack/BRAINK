from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import hashlib, json, os, sys, time


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _root(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


@dataclass(frozen=True)
class ObserverFrame:
    observer_identity: str
    observer_class: str
    scope: Mapping[str, Any]
    environment: Mapping[str, Any]
    phase: str
    observed_state: Mapping[str, Any]
    frame_root: str


class Observer2Runtime:
    """Situated environmental observer. It may interrogate, compare and continue; it may not mutate."""

    OBSERVER_CLASS = "SITUATED_ENVIRONMENT_OBSERVER"

    def __init__(self, observer_identity: str, scope: Mapping[str, Any], environment_root: str | Path):
        self.observer_identity = observer_identity
        self.scope = dict(scope)
        self.environment_root = Path(environment_root).resolve()
        self.prior_frame: ObserverFrame | None = None
        self.continuation = "UNSET"

    def _filesystem_sample(self) -> dict[str, Any]:
        targets = self.scope.get("paths") or []
        out: dict[str, Any] = {}
        for rel in targets:
            p = (self.environment_root / rel).resolve()
            if self.environment_root not in p.parents and p != self.environment_root:
                out[rel] = {"exists": False, "error": "OUT_OF_SCOPE"}
                continue
            if not p.exists():
                out[rel] = {"exists": False}
                continue
            data = p.read_bytes() if p.is_file() else b""
            out[rel] = {
                "exists": True,
                "kind": "file" if p.is_file() else "directory",
                "sha256": hashlib.sha256(data).hexdigest() if p.is_file() else None,
                "bytes": len(data) if p.is_file() else None,
            }
        return out

    def _process_sample(self) -> dict[str, Any]:
        return {"pid": os.getpid(), "python": sys.version.split()[0], "cwd": str(Path.cwd().resolve())}

    def sample(self, phase: str) -> ObserverFrame:
        observed = {
            "filesystem": self._filesystem_sample(),
            "process": self._process_sample(),
            "sampled_at_ns": time.time_ns(),
        }
        base = {
            "observer_identity": self.observer_identity,
            "observer_class": self.OBSERVER_CLASS,
            "scope": self.scope,
            "environment": {"root": str(self.environment_root)},
            "phase": phase,
            "observed_state": observed,
        }
        frame = ObserverFrame(**base, frame_root=_root(base))
        self.prior_frame = frame
        return frame

    def discrepancy(self, frame: ObserverFrame, expected: Mapping[str, Any]) -> dict[str, Any]:
        missing: list[str] = []
        mismatched: list[str] = []
        files = frame.observed_state["filesystem"]
        for rel, rule in expected.get("paths", {}).items():
            actual = files.get(rel, {"exists": False})
            if rule.get("exists") is True and not actual.get("exists"):
                missing.append(rel)
            if rule.get("exists") is False and actual.get("exists"):
                mismatched.append(rel)
            if rule.get("sha256") and actual.get("sha256") != rule["sha256"]:
                mismatched.append(rel)
        return {
            "missing": missing,
            "mismatched": sorted(set(mismatched)),
            "resolved": not missing and not mismatched,
            "frame_root": frame.frame_root,
        }

    @staticmethod
    def compare(pre: ObserverFrame, post: ObserverFrame) -> dict[str, Any]:
        before = pre.observed_state["filesystem"]
        after = post.observed_state["filesystem"]
        changes = []
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                changes.append({"path": key, "before": before.get(key), "after": after.get(key)})
        return {
            "pre_frame_root": pre.frame_root,
            "post_frame_root": post.frame_root,
            "changed": bool(changes),
            "changes": changes,
        }

    def update_continuation(self, *, discrepancy_post: Mapping[str, Any], comparison: Mapping[str, Any], invariants_survived: bool) -> str:
        if not invariants_survived:
            self.continuation = "REJECT_CANDIDATE"
        elif discrepancy_post.get("resolved") and comparison.get("changed"):
            self.continuation = "FOLLOW_SUCCESSOR_STATE"
        elif discrepancy_post.get("resolved") and not comparison.get("changed"):
            self.continuation = "ACTION_NOT_EFFECTIVE"
        else:
            self.continuation = "RECONCILE"
        return self.continuation

    def descriptor(self) -> dict[str, Any]:
        return {
            "IDENTITY": {"observer_identity": self.observer_identity, "class": self.OBSERVER_CLASS, "role": "environmental interrogation"},
            "STATE": {"bound": True, "last_environmental_frame": asdict(self.prior_frame) if self.prior_frame else None},
            "CAPABILITY": ["environment.sample", "state.compare", "discrepancy.emit", "continuation.update"],
            "ADDRESS": str(self.environment_root),
            "AUTHORITY": {"may_observe": True, "may_mutate": False},
            "PROCESS": "fresh environmental interrogation",
            "CONTINUATION": "sample -> compare -> discrepancy -> think -> mirror -> learn -> resample -> continue",
        }
