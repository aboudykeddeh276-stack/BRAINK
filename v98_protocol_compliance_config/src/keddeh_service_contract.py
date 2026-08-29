from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol


class KeddehService(Protocol):
    def recognize(self) -> bool: ...
    def execute(self) -> bool: ...
    def verify(self) -> bool: ...
    def write_receipt(self) -> bool: ...
    def readback(self) -> bool: ...
    def handoff(self) -> bool: ...


@dataclass(frozen=True)
class ServiceContractResult:
    service_id: str
    recognize: bool
    execute: bool
    verify: bool
    write_receipt: bool
    readback: bool
    handoff: bool

    @property
    def passed(self) -> bool:
        return all([
            self.recognize,
            self.execute,
            self.verify,
            self.write_receipt,
            self.readback,
            self.handoff,
        ])

    def as_stage_map(self) -> Dict[str, bool]:
        return {
            "recognize": self.recognize,
            "execute": self.execute,
            "verify": self.verify,
            "write_receipt": self.write_receipt,
            "readback": self.readback,
            "handoff": self.handoff,
        }
