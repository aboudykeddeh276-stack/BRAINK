"""BrAInK runtime proof package.

Stdlib-only, deterministic runtime demonstrating: linguistic intent mapping,
canonical identity, a hash-chained durable ledger, a bounded signing surface,
raw DNS transport and restart recovery — each with honest proof status.
"""

from __future__ import annotations

__version__ = "1.0.0"
version = __version__  # convenience alias; kept in sync by construction

from .canonical import (
    canonical_bytes,
    canonical_hash,
    canonical_serialize,
    stable_namespace,
)
from .dns_transport import (
    DNSProofReceipt,
    DNSRecord,
    DNSTransport,
    build_query,
    encode_name,
    parse_response,
)
from .identity import (
    CollisionError,
    IdentityRegistry,
    detect_collision,
    generate_component_id,
    generate_service_id,
    generate_skill_id,
)
from .ledger import GENESIS_HASH, Ledger, LedgerEntry
from .linguistic_core import LEXICON_V1, LexiconVersion, LinguisticCore
from .receipts import (
    generate_package_manifest,
    generate_test_results,
    generate_validation_receipt,
)
from .restart import RestartManager, RestartState
from .runtime import BrAInKRuntime
from .signer import (
    ProductionSignerPlaceholder,
    SignatureEnvelope,
    TestSigner,
    prepare_canonical_payload,
)

__all__ = [
    "__version__",
    "version",
    # canonical
    "canonical_serialize",
    "canonical_bytes",
    "canonical_hash",
    "stable_namespace",
    # linguistic
    "LinguisticCore",
    "LexiconVersion",
    "LEXICON_V1",
    # identity
    "generate_component_id",
    "generate_skill_id",
    "generate_service_id",
    "detect_collision",
    "IdentityRegistry",
    "CollisionError",
    # ledger
    "Ledger",
    "LedgerEntry",
    "GENESIS_HASH",
    # signer
    "SignatureEnvelope",
    "TestSigner",
    "ProductionSignerPlaceholder",
    "prepare_canonical_payload",
    # dns
    "DNSRecord",
    "DNSProofReceipt",
    "DNSTransport",
    "build_query",
    "encode_name",
    "parse_response",
    # restart
    "RestartState",
    "RestartManager",
    # receipts
    "generate_package_manifest",
    "generate_test_results",
    "generate_validation_receipt",
    # runtime
    "BrAInKRuntime",
]
