from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import hashlib, json, time, uuid


def root(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Genome:
    genome_id: str
    undertaking: str
    genes: tuple[str, ...]
    capability_root: str
    created_ns: int


@dataclass(frozen=True)
class ServicePair:
    left: str
    right: str
    shared_genes: tuple[str, ...]
    complementary_genes: tuple[str, ...]
    pair_score: float
    pair_root: str


class ServiceGenomeEngine:
    """Pairs reusable service genes across functions, sectors and business undertakings."""

    def __init__(self, catalog: Dict[str, Any]):
        self.catalog = catalog

    def genome(self, undertaking: str, extra_genes: List[str] | None = None) -> Genome:
        base = list(self.catalog["undertaking_templates"][undertaking])
        genes = tuple(sorted(set(base + (extra_genes or []))))
        caps = sorted({cap for gid in genes for cap in self.catalog["genes"][gid]["provides"]})
        return Genome("GEN-" + uuid.uuid4().hex[:16], undertaking, genes, root(caps), time.time_ns())

    def pair(self, left: Genome, right: Genome) -> ServicePair:
        a, b = set(left.genes), set(right.genes)
        shared = tuple(sorted(a & b))
        complementary = tuple(sorted((a | b) - (a & b)))
        score = round((len(shared) / max(1, len(a | b))) * 0.75 + (min(len(complementary), 8) / 8) * 0.25, 6)
        body = {"left": left.undertaking, "right": right.undertaking, "shared": shared, "complementary": complementary, "score": score}
        return ServicePair(left.undertaking, right.undertaking, shared, complementary, score, root(body))

    def capability_map(self, genome: Genome) -> Dict[str, List[str]]:
        return {gid: list(self.catalog["genes"][gid]["provides"]) for gid in genome.genes}
