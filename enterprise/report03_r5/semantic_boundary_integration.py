#!/usr/bin/env python3
"""Cross-layer IL-LLM -> KEX -> ToT -> directory -> Layer-2 -> binary boundary.

Truth boundary:
- IL-LLM owns semantic meaning and semantic_digest.
- KEX translates and carries the accepted semantic identity.
- HTML is a symbolic projection/manifestation, not the semantic authority.
- bytes are produced only by explicit binary substrate materialization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib, json, os, struct

from resident_il_llm import (
    ResidentILLMAdapter, KEXSemanticTranslator, KEXConcept,
    HTMLConceptProjector, canonical_json_bytes, sha256_hex,
)
from distributed_coordinate_directory import DirectoryCluster
from layer2_closed_loop import ClosedLoopReconciler, SandboxActuator
from tot_process_cluster import ProcessCluster
from tot_safety_kernel import canonical, h

SCHEMA = "keddeh.report03.semantic-boundary-integration.v1"
MAGIC = b"KXBD"
VERSION = 2
MODE_RAW = 0
MODE_AB = 1
HEADER = struct.Struct(">4sBBQI8s32s")


class SemanticBoundaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ABToken:
    symbol: str
    count: int
    def __post_init__(self):
        if self.symbol not in ("A", "B") or not (1 <= self.count <= 9):
            raise ValueError("INVALID_AB_TOKEN")


def bytes_to_bits(data: bytes) -> str:
    return "".join(f"{b:08b}" for b in data)


def bits_to_bytes(bits: str) -> bytes:
    if any(c not in "01" for c in bits) or len(bits) % 8:
        raise ValueError("INVALID_BYTE_ALIGNED_BITS")
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))


def encode_ab(bits: str) -> tuple[ABToken, ...]:
    if any(c not in "01" for c in bits):
        raise ValueError("NON_BINARY_INPUT")
    if not bits:
        return ()
    out: list[ABToken] = []
    i = 0
    while i < len(bits):
        bit = bits[i]; j = i + 1
        while j < len(bits) and bits[j] == bit:
            j += 1
        remaining = j - i; sym = "A" if bit == "1" else "B"
        while remaining:
            n = min(9, remaining); out.append(ABToken(sym, n)); remaining -= n
        i = j
    return tuple(out)


def decode_ab(tokens: tuple[ABToken, ...]) -> str:
    bits = "".join(("1" if t.symbol == "A" else "0") * t.count for t in tokens)
    if encode_ab(bits) != tokens:
        raise ValueError("NON_CANONICAL_AB_STREAM")
    return bits


def pack_ab(tokens: tuple[ABToken, ...]) -> bytes:
    acc = 0; nbits = 0; out = bytearray()
    for t in tokens:
        code = ((1 if t.symbol == "A" else 0) << 4) | t.count
        acc = (acc << 5) | code; nbits += 5
        while nbits >= 8:
            shift = nbits - 8; out.append((acc >> shift) & 0xFF)
            acc = acc & ((1 << shift) - 1) if shift else 0; nbits = shift
    if nbits:
        out.append((acc << (8 - nbits)) & 0xFF)
    return bytes(out)


def unpack_ab(payload: bytes, token_count: int) -> tuple[ABToken, ...]:
    bitstream = "".join(f"{b:08b}" for b in payload)
    needed = token_count * 5
    if len(bitstream) < needed:
        raise ValueError("AB_PAYLOAD_TRUNCATED")
    out=[]
    for i in range(0, needed, 5):
        code=int(bitstream[i:i+5],2); count=code & 0x0F
        out.append(ABToken("A" if code & 0x10 else "B", count))
    tokens=tuple(out); decode_ab(tokens)
    return tokens


def _pack_raw(bits: str) -> bytes:
    if any(c not in "01" for c in bits): raise ValueError("NON_BINARY_INPUT")
    padded=bits + "0"*((-len(bits))%8)
    return bytes(int(padded[i:i+8],2) for i in range(0,len(padded),8)) if padded else b""


def _unpack_raw(payload: bytes, bit_length: int) -> str:
    if bit_length > len(payload)*8: raise ValueError("RAW_PAYLOAD_TRUNCATED")
    return "".join(f"{b:08b}" for b in payload)[:bit_length]


@dataclass(frozen=True)
class BinaryReceipt:
    schema: str
    semantic_digest: str
    encoding: str
    source_bytes: int
    wire_bytes: int
    ab_token_count: int
    source_sha256: str
    wire_sha256: str
    roundtrip_equal: bool


class ExplicitBinaryBoundary:
    """Only this object lowers symbolic bytes into a substrate packet."""
    @classmethod
    def encode(cls, source: bytes, semantic_digest: str) -> tuple[bytes, BinaryReceipt]:
        if len(semantic_digest) != 64:
            raise SemanticBoundaryError("SEMANTIC_DIGEST_INVALID")
        bits=bytes_to_bits(source); tokens=encode_ab(bits); ab=pack_ab(tokens); raw=_pack_raw(bits)
        if len(ab) < len(raw):
            mode=MODE_AB; payload=ab; token_count=len(tokens); enc="KEX_AB"
        else:
            mode=MODE_RAW; payload=raw; token_count=0; enc="RAW_BINARY"
        digest=hashlib.sha256(payload).digest(); prefix=bytes.fromhex(semantic_digest)[:8]
        wire=HEADER.pack(MAGIC,VERSION,mode,len(bits),token_count,prefix,digest)+payload
        recovered,meta=cls.decode(wire,expected_semantic_digest=semantic_digest)
        receipt=BinaryReceipt(
            schema=SCHEMA, semantic_digest=semantic_digest, encoding=enc,
            source_bytes=len(source), wire_bytes=len(wire), ab_token_count=len(tokens),
            source_sha256=sha256_hex(source), wire_sha256=sha256_hex(wire),
            roundtrip_equal=(recovered==source),
        )
        return wire,receipt

    @classmethod
    def decode(cls, wire: bytes, *, expected_semantic_digest: str) -> tuple[bytes,dict[str,Any]]:
        if len(wire)<HEADER.size: raise SemanticBoundaryError("BOUNDARY_PACKET_TRUNCATED")
        magic,version,mode,bit_length,token_count,prefix,digest=HEADER.unpack(wire[:HEADER.size])
        if magic!=MAGIC or version!=VERSION: raise SemanticBoundaryError("BOUNDARY_HEADER_INVALID")
        expected_prefix=bytes.fromhex(expected_semantic_digest)[:8]
        if prefix!=expected_prefix: raise SemanticBoundaryError("SEMANTIC_DIGEST_PREFIX_MISMATCH")
        payload=wire[HEADER.size:]
        if hashlib.sha256(payload).digest()!=digest: raise SemanticBoundaryError("BOUNDARY_PAYLOAD_DIGEST_MISMATCH")
        if mode==MODE_AB:
            bits=decode_ab(unpack_ab(payload,token_count)); enc="KEX_AB"
        elif mode==MODE_RAW:
            bits=_unpack_raw(payload,bit_length); enc="RAW_BINARY"
        else: raise SemanticBoundaryError("BOUNDARY_MODE_UNKNOWN")
        if len(bits)!=bit_length: raise SemanticBoundaryError("BOUNDARY_BIT_LENGTH_MISMATCH")
        if len(bits)%8: raise SemanticBoundaryError("BOUNDARY_NOT_BYTE_ALIGNED")
        return bits_to_bytes(bits),{"encoding":enc,"bit_length":bit_length,"semantic_digest_prefix":prefix.hex(),"payload_sha256":digest.hex()}


class BinarySubstrateActuator:
    """Concrete byte-constrained sink with atomic replacement and readback."""
    def __init__(self, root: str|Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def materialize(self, rel: str, source: bytes, semantic_digest: str) -> dict[str,Any]:
        wire,receipt=ExplicitBinaryBoundary.encode(source,semantic_digest)
        target=self.root/rel; target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_name(target.name+".tmp")
        with open(tmp,"wb") as f: f.write(wire); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,target)
        fd=os.open(target.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        recovered,meta=ExplicitBinaryBoundary.decode(target.read_bytes(),expected_semantic_digest=semantic_digest)
        if recovered!=source: raise SemanticBoundaryError("BINARY_SUBSTRATE_READBACK_MISMATCH")
        return {"state":"BINARY_SUBSTRATE_MATERIALIZED","path":str(target),"receipt":asdict(receipt),"readback":meta}


class SemanticBoundaryController:
    def __init__(self, adapter: ResidentILLMAdapter):
        self.adapter=adapter; self.translator=KEXSemanticTranslator(adapter)

    def concept(self,symbol:str)->KEXConcept:
        return self.translator.translate(symbol,require_clean=True)

    @staticmethod
    def logical_coordinate(concept:KEXConcept)->str:
        row=int(concept.meaning["source_row"])
        return f"KEX://ILLLM/CONCEPT/{concept.symbol.upper().replace(' ','_')}/ROW/{row}"

    @staticmethod
    def validate_concept(concept:KEXConcept)->None:
        actual=sha256_hex(canonical_json_bytes(concept.meaning))
        if actual!=concept.semantic_digest: raise SemanticBoundaryError("SEMANTIC_DIGEST_MISMATCH")
        if concept.kex_route!="KEX-L-TRANS": raise SemanticBoundaryError(f"UNEXPECTED_KEX_ROUTE:{concept.kex_route}")

    def authority_payload(self,concept:KEXConcept,html_text:str)->dict[str,Any]:
        self.validate_concept(concept)
        return {
          "semantic_owner":"IL-LLM", "translation_owner":"KEX",
          "boundary_policy":"SYMBOLIC_UNTIL_BINARY_REQUIRED",
          "symbol":concept.symbol,"semantic_digest":concept.semantic_digest,
          "resident_semantic_coordinate":concept.coordinate,"resident_coordinate_kind":concept.coordinate_kind,
          "kex_route":concept.kex_route,"source_locator":concept.source_locator,"source_status":concept.source_status,
          "html_sha256":sha256_hex(html_text.encode("utf-8")),
        }

    def define_accepted(self,cluster:ProcessCluster,concept:KEXConcept,reachable:tuple[str,...],*,title:str="KEX / IL-LLM Concept Projection")->dict[str,Any]:
        self.validate_concept(concept); html_text=HTMLConceptProjector.project([concept],title=title); coord=self.logical_coordinate(concept)
        metadata=self.authority_payload(concept,html_text)
        out=cluster.transition("COORDINATE_DEFINE",{
            "coordinate":coord,"kind":"ILLLM_SEMANTIC_CONCEPT",
            "desired":{"managed_files":{"concept.html":html_text}},"metadata":metadata,
        },reachable=reachable)
        return {"coordinate":coord,"concept":asdict(concept),"html":html_text,"metadata":metadata,"commit":out}

    def verify_accepted(self,directory:DirectoryCluster,replica_id:str,coordinate:str,concept:KEXConcept)->dict[str,Any]:
        self.validate_concept(concept); resolved=directory.resolve(replica_id,coordinate)
        if resolved["state"]!="RESOLVED_ACCEPTED_COORDINATE": raise SemanticBoundaryError("ACCEPTED_COORDINATE_MISSING")
        m=resolved["record"].get("metadata",{})
        for k,expected in {"semantic_owner":"IL-LLM","translation_owner":"KEX","semantic_digest":concept.semantic_digest,"resident_semantic_coordinate":concept.coordinate,"kex_route":concept.kex_route}.items():
            if m.get(k)!=expected: raise SemanticBoundaryError(f"ACCEPTED_SEMANTIC_METADATA_MISMATCH:{k}")
        return resolved

    def reconcile_html(self,directory:DirectoryCluster,replica_id:str,coordinate:str,manifestation_root:str|Path)->dict[str,Any]:
        actuator=SandboxActuator(manifestation_root)
        try:
            return ClosedLoopReconciler(directory,replica_id,actuator).reconcile_until_converged(coordinate)
        finally: actuator.close()

    def materialize_binary(self,directory:DirectoryCluster,replica_id:str,coordinate:str,concept:KEXConcept,source:bytes,sink:BinarySubstrateActuator,*,requires_binary:bool)->dict[str,Any]:
        resolved=self.verify_accepted(directory,replica_id,coordinate,concept)
        if not requires_binary:
            return {"state":"SYMBOLIC_PATH_NO_BINARY_MATERIALIZATION","semantic_digest":concept.semantic_digest,"accepted_state_root":resolved["accepted_state_root"]}
        out=sink.materialize("concept.kxbd",source,concept.semantic_digest)
        return {**out,"semantic_digest":concept.semantic_digest,"accepted_state_root":resolved["accepted_state_root"],"directory_root":resolved["directory_root"]}