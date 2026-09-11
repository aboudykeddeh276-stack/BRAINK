from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class Domain(str, Enum):
    SAAS_CONTROL = "SAAS_CONTROL"
    CASEPATH_BUSINESS = "CASEPATH_BUSINESS"
    CLAIMPATH_PRODUCT = "CLAIMPATH_PRODUCT"
    BRAINK_RUNTIME = "BRAINK_RUNTIME"
    KEX_RUNTIME = "KEX_RUNTIME"
    EPIC_GOVERNANCE = "EPIC_GOVERNANCE"
    DNTG_RESEARCH = "DNTG_RESEARCH"
    PUBLIC_PROJECTION = "PUBLIC_PROJECTION"
    EVIDENCE = "EVIDENCE"

class Relation(str, Enum):
    REQUIRES = "REQUIRES"
    INVOKES = "INVOKES"
    GOVERNS_CLAIM = "GOVERNS_CLAIM"
    PROJECTS = "PROJECTS"
    EMITS_EVIDENCE = "EMITS_EVIDENCE"
    FORBIDDEN = "FORBIDDEN"

@dataclass(frozen=True)
class BoundaryRule:
    source: Domain
    target: Domain
    relation: Relation
    allowed: bool
    reason: str

RULES = (
    BoundaryRule(Domain.CASEPATH_BUSINESS, Domain.SAAS_CONTROL, Relation.REQUIRES, True, "CasePath may request SaaS identity, billing, jobs, storage, and evidence services."),
    BoundaryRule(Domain.CLAIMPATH_PRODUCT, Domain.SAAS_CONTROL, Relation.REQUIRES, True, "ClaimPath declares SaaS dependency closure."),
    BoundaryRule(Domain.SAAS_CONTROL, Domain.BRAINK_RUNTIME, Relation.INVOKES, True, "Control plane may dispatch explicitly admitted BRAINK capabilities."),
    BoundaryRule(Domain.SAAS_CONTROL, Domain.KEX_RUNTIME, Relation.INVOKES, True, "Control plane may dispatch explicitly admitted KEX capabilities."),
    BoundaryRule(Domain.EPIC_GOVERNANCE, Domain.SAAS_CONTROL, Relation.GOVERNS_CLAIM, True, "EPIC may gate evidence and claim promotion but does not own SaaS state."),
    BoundaryRule(Domain.SAAS_CONTROL, Domain.PUBLIC_PROJECTION, Relation.PROJECTS, True, "SaaS may expose bounded user and admin projections."),
    BoundaryRule(Domain.SAAS_CONTROL, Domain.EVIDENCE, Relation.EMITS_EVIDENCE, True, "State mutations emit chained receipts."),
    BoundaryRule(Domain.DNTG_RESEARCH, Domain.SAAS_CONTROL, Relation.INVOKES, False, "DNTG mathematics has no authority over SaaS mutation paths."),
    BoundaryRule(Domain.DNTG_RESEARCH, Domain.CASEPATH_BUSINESS, Relation.INVOKES, False, "Research models cannot mutate CasePath business state."),
)

def permitted(source: Domain, target: Domain, relation: Relation) -> BoundaryRule:
    for rule in RULES:
        if (rule.source, rule.target, rule.relation) == (source, target, relation):
            return rule
    return BoundaryRule(source, target, relation, False, "No explicit relation grants this traversal.")
