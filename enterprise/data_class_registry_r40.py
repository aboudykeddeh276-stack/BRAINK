from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import hashlib
import json

ALLOWED_DATA_CLASSES = frozenset({
    "OBSERVATION", "CORRECTION", "COMMAND", "WORKLOAD", "SERVICE_DEFINITION",
    "MODEL_EXECUTION", "KNOWLEDGE_DELTA", "ARTIFACT", "TELEMETRY",
})

NODE_ELIGIBLE_CLASSES = frozenset({"WORKLOAD", "SERVICE_DEFINITION", "MODEL_EXECUTION"})
EXECUTION_ELIGIBLE_CLASSES = frozenset({
    "CORRECTION", "COMMAND", "WORKLOAD", "SERVICE_DEFINITION", "MODEL_EXECUTION",
})


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DataClassRecord:
    data_id: str
    data_class: str
    source: str
    schema_version: str
    sector: str | None
    payload_root: str
    logical_identity: str
    execution_eligible: bool
    node_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataClassRegistry:
    """Typed identity gate before node resolution/materialization."""

    def classify(
        self,
        *,
        source: str,
        data_class: str,
        payload: dict[str, Any],
        schema_version: str = "1",
        sector: str | None = None,
    ) -> DataClassRecord:
        if not isinstance(payload, dict):
            raise ValueError("DATA_PAYLOAD_MUST_BE_OBJECT")
        source = str(source).strip()
        if not source:
            raise ValueError("DATA_SOURCE_REQUIRED")
        normalized_class = str(data_class).strip().upper()
        if normalized_class not in ALLOWED_DATA_CLASSES:
            raise ValueError(f"INVALID_DATA_CLASS:{normalized_class}")
        schema_version = str(schema_version).strip()
        if not schema_version:
            raise ValueError("DATA_SCHEMA_VERSION_REQUIRED")
        sector_value = None if sector is None else str(sector).strip() or None
        payload_root = digest(payload)
        identity_material = {
            "source": source,
            "data_class": normalized_class,
            "schema_version": schema_version,
            "sector": sector_value,
            "payload_root": payload_root,
        }
        data_id = "DATA-" + digest(identity_material)[:24]
        logical_identity = f"data://{normalized_class.lower()}/{data_id}"
        return DataClassRecord(
            data_id=data_id,
            data_class=normalized_class,
            source=source,
            schema_version=schema_version,
            sector=sector_value,
            payload_root=payload_root,
            logical_identity=logical_identity,
            execution_eligible=normalized_class in EXECUTION_ELIGIBLE_CLASSES,
            node_eligible=normalized_class in NODE_ELIGIBLE_CLASSES,
        )
