from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class ObjectClass(str, Enum):
    ROOT='ROOT'; SUBSTRATE='SUBSTRATE'; RUNTIME='RUNTIME'; SERVICE='SERVICE'; REGISTRY='REGISTRY'; LEDGER='LEDGER'; NODE='NODE'; RESOURCE='RESOURCE'; OPERATION='OPERATION'; TEST='TEST'; POLICY='POLICY'; INTERFACE='INTERFACE'; PROJECTION='PROJECTION'; CARRIER='CARRIER'; EVIDENCE='EVIDENCE'; SCHEDULE='SCHEDULE'; INSTRUCTION='INSTRUCTION'

class EvidenceState(str, Enum):
    DECLARED='DECLARED'; SPECIFIED='SPECIFIED'; IMPLEMENTED='IMPLEMENTED'; BUILDABLE='BUILDABLE'; EXECUTED='EXECUTED'; OBSERVED='OBSERVED'; VERIFIED='VERIFIED'; DEPLOYED='DEPLOYED'

class RegistryObject(BaseModel):
    object_id: str
    object_class: ObjectClass
    logical_address: str | None = None
    parent_id: str | None = None
    implementation_surface: str | None = None
    carrier: dict[str, Any] | None = None
    interfaces: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.DECLARED
    metadata: dict[str, Any] = Field(default_factory=dict)

class ActionExecutionRequest(BaseModel):
    action: str
    target: str
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str
    expected_version: int | None = None

class MutationReceipt(BaseModel):
    request_id: str
    action: str
    target: str
    stages: list[str]
    before_hash: str
    after_hash: str
    mutation_hash: str
    version: int
    ledger_index: int
