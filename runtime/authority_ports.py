from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Any
from .braink_core import AuthorityError

@dataclass(frozen=True)
class AuthorityObservation:
    authority_class: str
    target: str
    state: str
    evidence: Mapping[str, Any]

class ExplicitAuthorityAdapter:
    """Observation and mutation are independent capabilities; observing never grants mutation."""
    def __init__(self, authority_class: str, observer, mutator=None):
        self.authority_class = authority_class
        self._observer = observer
        self._mutator = mutator
    def observe(self, target: str): return self._observer(target)
    def mutate(self, target: str, operation: Mapping[str, Any]):
        if self._mutator is None:
            raise AuthorityError(f"{self.authority_class} mutation authority not installed")
        return self._mutator(target, operation)
