from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "braink.cascade-topology.r40/v1"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hmac_sha256(key: bytes, payload: bytes) -> bytes:
    if not key:
        raise ValueError("SECRET_KEY_REQUIRED")
    return hmac.new(key, payload, digestmod=hashlib.sha256).digest()


@dataclass(frozen=True)
class CascadeNode:
    node_id: str
    layer: int
    branch_path: tuple[int, ...]
    parent_id: str | None
    root_id: str
    identity_root: str


@dataclass(frozen=True)
class LinkRole:
    source: str
    target: str
    role: str  # parent | root_anchor

    def undirected_key(self) -> tuple[str, str]:
        return tuple(sorted((self.source, self.target)))


@dataclass
class CascadeTopology:
    root_seed: str
    branching_factor: int = 3
    depth: int = 3
    root_id: str = "NODE_L0_ROOT"
    nodes: dict[str, CascadeNode] = field(default_factory=dict)
    link_roles: list[LinkRole] = field(default_factory=list)

    def metrics(self) -> dict[str, Any]:
        layer_distribution: dict[int, int] = {}
        for node in self.nodes.values():
            layer_distribution[node.layer] = layer_distribution.get(node.layer, 0) + 1
        unique_edges = {link.undirected_key() for link in self.link_roles}
        directed_adjacency_entries = 2 * len(unique_edges)
        return {
            "schema": SCHEMA,
            "branching_factor": self.branching_factor,
            "depth": self.depth,
            "total_nodes": len(self.nodes),
            "layer_distribution": dict(sorted(layer_distribution.items())),
            "logical_link_roles": len(self.link_roles),
            "unique_undirected_edges": len(unique_edges),
            "directed_adjacency_entries": directed_adjacency_entries,
            "mean_unique_degree": (directed_adjacency_entries / len(self.nodes)) if self.nodes else 0.0,
        }

    def verify(self) -> dict[str, Any]:
        if self.branching_factor < 1:
            return {"status": "FAILED:INVALID_BRANCHING_FACTOR"}
        if self.depth < 0:
            return {"status": "FAILED:INVALID_DEPTH"}

        expected_nodes = sum(self.branching_factor ** layer for layer in range(self.depth + 1))
        expected_roles = sum(2 * (self.branching_factor ** layer) for layer in range(1, self.depth + 1))
        # Layer-1 parent and root-anchor roles resolve to the same physical edge.
        expected_unique_edges = expected_roles - self.branching_factor

        metrics = self.metrics()
        if metrics["total_nodes"] != expected_nodes:
            return {"status": "FAILED:NODE_COUNT", "expected": expected_nodes, "observed": metrics["total_nodes"]}
        if metrics["logical_link_roles"] != expected_roles:
            return {"status": "FAILED:LINK_ROLE_COUNT", "expected": expected_roles, "observed": metrics["logical_link_roles"]}
        if metrics["unique_undirected_edges"] != expected_unique_edges:
            return {"status": "FAILED:UNIQUE_EDGE_COUNT", "expected": expected_unique_edges, "observed": metrics["unique_undirected_edges"]}

        for node in self.nodes.values():
            if node.layer != len(node.branch_path):
                return {"status": "FAILED:LAYER_PATH_MISMATCH", "node_id": node.node_id}
            if node.layer == 0:
                if node.parent_id is not None:
                    return {"status": "FAILED:ROOT_HAS_PARENT"}
                continue
            roles = [link for link in self.link_roles if link.source == node.node_id]
            if sum(link.role == "parent" for link in roles) != 1:
                return {"status": "FAILED:PARENT_LINK_ROLE", "node_id": node.node_id}
            if sum(link.role == "root_anchor" for link in roles) != 1:
                return {"status": "FAILED:ROOT_LINK_ROLE", "node_id": node.node_id}

        return {"status": "VALIDATED", **metrics}


class CascadePlanner:
    """Deterministic topology planner only.

    It does not spawn processes, open sockets, or claim distributed consensus.
    Activation belongs to the resident resource scheduler and fabric admission path.
    """

    def __init__(self, *, root_seed: str, secret_key: bytes, branching_factor: int = 3, depth: int = 3):
        if not root_seed:
            raise ValueError("ROOT_SEED_REQUIRED")
        if not secret_key:
            raise ValueError("SECRET_KEY_REQUIRED")
        if branching_factor < 1:
            raise ValueError("BRANCHING_FACTOR_MUST_BE_POSITIVE")
        if depth < 0:
            raise ValueError("DEPTH_MUST_BE_NONNEGATIVE")
        self.root_seed = root_seed
        self.secret_key = secret_key
        self.branching_factor = int(branching_factor)
        self.depth = int(depth)

    def _identity(self, branch_path: tuple[int, ...], parent_id: str | None, root_id: str) -> tuple[str, str]:
        envelope = {
            "schema": SCHEMA,
            "root_seed": self.root_seed,
            "branch_path": list(branch_path),
            "parent_id": parent_id,
            "root_id": root_id,
        }
        digest = hmac_sha256(self.secret_key, canonical_json(envelope))
        layer = len(branch_path)
        suffix = digest.hex()[:16]
        label = "root" if not branch_path else "-".join(str(x) for x in branch_path)
        return f"node-l{layer}-{label}-{suffix}", digest.hex()

    def build(self) -> CascadeTopology:
        root_id, root_identity = self._identity((), None, "ROOT")
        topology = CascadeTopology(
            root_seed=self.root_seed,
            branching_factor=self.branching_factor,
            depth=self.depth,
            root_id=root_id,
        )
        root = CascadeNode(root_id, 0, (), None, root_id, root_identity)
        topology.nodes[root_id] = root

        frontier = [root]
        while frontier:
            parent = frontier.pop(0)
            if parent.layer >= self.depth:
                continue
            for branch in range(1, self.branching_factor + 1):
                path = parent.branch_path + (branch,)
                node_id, identity_root = self._identity(path, parent.node_id, root_id)
                if node_id in topology.nodes:
                    raise RuntimeError("DUPLICATE_NODE_ID")
                child = CascadeNode(node_id, parent.layer + 1, path, parent.node_id, root_id, identity_root)
                topology.nodes[node_id] = child
                topology.link_roles.append(LinkRole(node_id, parent.node_id, "parent"))
                topology.link_roles.append(LinkRole(node_id, root_id, "root_anchor"))
                frontier.append(child)

        return topology

    @staticmethod
    def activation_layers(topology: CascadeTopology) -> list[list[str]]:
        batches: list[list[str]] = []
        for layer in range(topology.depth + 1):
            batches.append(sorted(node.node_id for node in topology.nodes.values() if node.layer == layer))
        return batches
