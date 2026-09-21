from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from html import escape
import json
import struct
from typing import Any, Mapping

from .ab_binary_codec import decode_blocks, encode_bits, encode_tokens, pack_18_symbol, parse_tokens, unpack_18_symbol

SCHEMA = "kex.symbolic-envelope.v1"
HTML_SCHEMA = "kex.html-concept-projection.v1"
WIRE_MAGIC = b"KAB1"
WIRE_VERSION = 1
WIRE_MODE_PACKED18 = 1


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class SemanticEntry:
    symbol_id: str
    lexical_form: str
    semantic_type: str
    grammar_role: str
    definition: str
    policy_version: str = "IL_LLM_SYMBOL_DICTIONARY_V1"


class ILLLMSemanticDictionary:
    """Bounded semantic dictionary/grammar binding for KEX symbols.

    IL-LLM owns meaning and grammar. KEX consumes the registered semantic entry
    but does not mutate its meaning while changing representation.
    """
    def __init__(self, entries: tuple[SemanticEntry, ...] = ()) -> None:
        self._entries: dict[str, SemanticEntry] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: SemanticEntry) -> None:
        if not entry.symbol_id or not entry.lexical_form or not entry.semantic_type or not entry.grammar_role:
            raise ValueError("ILLLM_SEMANTIC_ENTRY_INCOMPLETE")
        prior = self._entries.get(entry.symbol_id)
        if prior is not None and prior != entry:
            raise ValueError("ILLLM_SYMBOL_REDEFINITION_REJECTED")
        self._entries[entry.symbol_id] = entry

    def resolve(self, symbol_id: str) -> SemanticEntry:
        try:
            return self._entries[symbol_id]
        except KeyError as exc:
            raise ValueError("ILLLM_SYMBOL_UNKNOWN") from exc

    def dictionary_root(self) -> str:
        return root({key: asdict(value) for key, value in sorted(self._entries.items())})


@dataclass(frozen=True)
class SymbolicEnvelope:
    schema: str
    concept_id: str
    symbol_id: str
    lexical_form: str
    semantic_type: str
    grammar_role: str
    meaning: str
    semantic_root: str
    dictionary_root: str
    source_projection_root: str | None
    attributes: Mapping[str, Any]
    ab_tokens: str
    raw_bit_count: int
    envelope_root: str

    def identity_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("envelope_root", None)
        return value


def _bytes_to_bits(payload: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in payload)


def _bits_to_bytes(bits: str) -> bytes:
    if len(bits) % 8:
        raise ValueError("KEX_SYMBOLIC_RAW_BITS_NOT_BYTE_ALIGNED")
    if not bits:
        return b""
    return int(bits, 2).to_bytes(len(bits) // 8, "big")


def bind_symbol(
    dictionary: ILLLMSemanticDictionary,
    *,
    concept_id: str,
    symbol_id: str,
    attributes: Mapping[str, Any] | None = None,
    source_projection: Mapping[str, Any] | None = None,
) -> SymbolicEnvelope:
    entry = dictionary.resolve(symbol_id)
    attrs = dict(attributes or {})
    source_root = None
    if source_projection is not None:
        source_root = str(source_projection.get("semantic_root") or root(source_projection))
    semantic_payload = {
        "concept_id": concept_id,
        "entry": asdict(entry),
        "attributes": attrs,
        "source_projection_root": source_root,
        "dictionary_root": dictionary.dictionary_root(),
    }
    semantic_root = root(semantic_payload)
    symbolic_payload = {
        "schema": SCHEMA,
        "concept_id": concept_id,
        "symbol_id": entry.symbol_id,
        "lexical_form": entry.lexical_form,
        "semantic_type": entry.semantic_type,
        "grammar_role": entry.grammar_role,
        "meaning": entry.definition,
        "semantic_root": semantic_root,
        "dictionary_root": dictionary.dictionary_root(),
        "source_projection_root": source_root,
        "attributes": attrs,
    }
    raw = canonical(symbolic_payload)
    bits = _bytes_to_bits(raw)
    tokens = encode_tokens(bits)
    identity = {**symbolic_payload, "ab_tokens": tokens, "raw_bit_count": len(bits)}
    return SymbolicEnvelope(**identity, envelope_root=root(identity))


def project_html(envelope: SymbolicEnvelope) -> str:
    """Project a symbolic KEX concept into deterministic HTML.

    The AB stream stays textual/symbolic here. No packed bytes are emitted.
    """
    attrs = escape(json.dumps(dict(envelope.attributes), sort_keys=True, separators=(",", ":"), ensure_ascii=False), quote=True)
    return (
        f'<article data-kex-schema="{HTML_SCHEMA}" '
        f'data-kex-concept-id="{escape(envelope.concept_id, quote=True)}" '
        f'data-illlm-symbol-id="{escape(envelope.symbol_id, quote=True)}" '
        f'data-illlm-semantic-root="{envelope.semantic_root}" '
        f'data-illlm-dictionary-root="{envelope.dictionary_root}" '
        f'data-kex-envelope-root="{envelope.envelope_root}" '
        f'data-kex-ab="{envelope.ab_tokens}" '
        f'data-kex-raw-bit-count="{envelope.raw_bit_count}" '
        f'data-kex-attributes="{attrs}">'
        f'<span data-kex-role="{escape(envelope.grammar_role, quote=True)}" '
        f'data-kex-semantic-type="{escape(envelope.semantic_type, quote=True)}">'
        f'{escape(envelope.lexical_form)}</span></article>'
    )


class BinaryBoundaryAdapter:
    """Explicit KEX boundary from symbolic A/B form to byte-constrained carriers."""

    HEADER = struct.Struct(">4sBBII32s32s")

    @classmethod
    def emit(cls, envelope: SymbolicEnvelope) -> bytes:
        blocks = parse_tokens(envelope.ab_tokens)
        packed, packed_bit_count = pack_18_symbol(blocks)
        envelope_root_bytes = bytes.fromhex(envelope.envelope_root)
        packed_hash = sha256(packed).digest()
        header = cls.HEADER.pack(
            WIRE_MAGIC,
            WIRE_VERSION,
            WIRE_MODE_PACKED18,
            envelope.raw_bit_count,
            packed_bit_count,
            envelope_root_bytes,
            packed_hash,
        )
        return header + packed

    @classmethod
    def restore_symbolic_payload(cls, wire: bytes) -> tuple[dict[str, Any], str]:
        if len(wire) < cls.HEADER.size:
            raise ValueError("KEX_BINARY_BOUNDARY_TRUNCATED")
        magic, version, mode, raw_bit_count, packed_bit_count, expected_root, expected_packed_hash = cls.HEADER.unpack(wire[: cls.HEADER.size])
        if magic != WIRE_MAGIC or version != WIRE_VERSION or mode != WIRE_MODE_PACKED18:
            raise ValueError("KEX_BINARY_BOUNDARY_HEADER_INVALID")
        packed = wire[cls.HEADER.size :]
        if sha256(packed).digest() != expected_packed_hash:
            raise ValueError("KEX_BINARY_BOUNDARY_PACKED_HASH_MISMATCH")
        blocks = unpack_18_symbol(packed, packed_bit_count)
        bits = decode_blocks(blocks)
        if len(bits) != raw_bit_count:
            raise ValueError("KEX_BINARY_BOUNDARY_RAW_LENGTH_MISMATCH")
        raw = _bits_to_bytes(bits)
        payload = json.loads(raw.decode("utf-8"))
        tokens = encode_tokens(bits)
        identity = {**payload, "ab_tokens": tokens, "raw_bit_count": raw_bit_count}
        restored_root = root(identity)
        if restored_root != expected_root.hex():
            raise ValueError("KEX_BINARY_BOUNDARY_ROOT_MISMATCH")
        return payload, tokens


def from_linguistic_projection(
    dictionary: ILLLMSemanticDictionary,
    projection: Mapping[str, Any],
    *,
    concept_id: str,
    symbol_id: str,
    attributes: Mapping[str, Any] | None = None,
) -> SymbolicEnvelope:
    if "semantic_root" not in projection:
        raise ValueError("ILLLM_PROJECTION_SEMANTIC_ROOT_REQUIRED")
    truth = projection.get("truth_boundary", {})
    if truth.get("projection_mutates_source") is not False:
        raise ValueError("ILLLM_SOURCE_MUTATION_BOUNDARY_INVALID")
    merged = dict(attributes or {})
    merged["linguistic_projection"] = projection.get("projection", {})
    merged["anchor"] = projection.get("anchor", {})
    merged["relation"] = projection.get("relation", {})
    return bind_symbol(
        dictionary,
        concept_id=concept_id,
        symbol_id=symbol_id,
        attributes=merged,
        source_projection=projection,
    )
