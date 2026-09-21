#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "kex.report03.symbolic-boundary.v1"
AB_MAGIC = b"KAB1"
AB_VERSION = 1
ERROR_MARKERS = {"#REF!", "#NUM!", "#VALUE!", "#NAME?", "#N/A", "#DIV/0!"}

class BoundaryError(ValueError):
    pass

class SemanticResolutionError(BoundaryError):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    # Project-local deterministic JSON profile. Not a claim of RFC 8785 conformance.
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _cell_rows(cells: list[list[dict[str, Any]]]) -> dict[int, dict[str, dict[str, Any]]]:
    rows: dict[int, dict[str, dict[str, Any]]] = {}
    for row in cells:
        for cell in row:
            m = re.fullmatch(r"([A-Z]+)(\d+)", str(cell.get("cell", "")))
            if not m:
                continue
            rows.setdefault(int(m.group(2)), {})[m.group(1)] = cell
    return rows


def _value(row: dict[str, dict[str, Any]], col: str) -> str:
    v = row.get(col, {}).get("value", "")
    return "" if v is None else str(v)


def _has_error(row: dict[str, dict[str, Any]]) -> bool:
    return any(_value(row, c).strip() in ERROR_MARKERS for c in row)


@dataclass(frozen=True)
class SemanticRecord:
    entity: str
    entity_type: str
    dictionary_meaning: str
    thesaurus: str
    concept: str
    analogy: str
    routing_hash: str
    core_meaning: str
    environment: str
    observer_perspective: str
    composition: str
    effect: str
    objectivity_state: str
    source_sheet: str
    source_row: int
    source_status: str

    def semantic_payload(self) -> dict[str, Any]:
        return asdict(self)


class ResidentILLMAdapter:
    """Read-only executable adapter over recovered resident IL-LLM workbook surfaces.

    It does not claim to be the whole IL-LLM. It preserves source location and source
    defects and refuses to fabricate missing dictionary entries.
    """

    def __init__(self, recovered_cells_path: str | Path):
        self.path = Path(recovered_cells_path)
        self.raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.lexicon: dict[str, SemanticRecord] = {}
        self.recovered_router: dict[str, dict[str, str]] = {}
        self.translators: dict[str, dict[str, str]] = {}
        self.runtime_registers: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        lex_rows = _cell_rows(self.raw.get("02 - Words (English Lexicon)", []))
        for n, row in sorted(lex_rows.items()):
            if n == 1:
                continue
            entity = _value(row, "A").strip()
            if not entity:
                continue
            status = "DEGRADED_SOURCE" if _has_error(row) else "SOURCE_OK"
            rec = SemanticRecord(
                entity=entity,
                entity_type=_value(row, "B"),
                dictionary_meaning=_value(row, "C"),
                thesaurus=_value(row, "D"),
                concept=_value(row, "E"),
                analogy=_value(row, "F"),
                routing_hash=_value(row, "G"),
                core_meaning=_value(row, "H"),
                environment=_value(row, "I"),
                observer_perspective=_value(row, "J"),
                composition=_value(row, "K"),
                effect=_value(row, "L"),
                objectivity_state=_value(row, "M"),
                source_sheet="02 - Words (English Lexicon)",
                source_row=n,
                source_status=status,
            )
            key = entity.casefold()
            # First resident row wins; duplicates are retained as a detected source issue.
            self.lexicon.setdefault(key, rec)

        router_rows = _cell_rows(self.raw.get("BRAINK_LEXICON_ROUTER_RECOVERED", []))
        for n, row in sorted(router_rows.items()):
            if n == 1:
                continue
            fn = _value(row, "B").strip()
            if not fn:
                continue
            self.recovered_router[fn.casefold()] = {
                "routing_hash": _value(row, "A"),
                "function": fn,
                "meaning": _value(row, "C"),
                "concept": _value(row, "D"),
                "recovery_state": _value(row, "E"),
                "source": _value(row, "F"),
                "source_row": str(n),
            }

        tx_rows = _cell_rows(self.raw.get("KEX TRANSLATORS", []))
        for n, row in sorted(tx_rows.items()):
            if n == 1:
                continue
            # Sheet packs four translator groups in A:D, E:H, I:L, M:P.
            for cols in (("A","B","C","D"),("E","F","G","H"),("I","J","K","L"),("M","N","O","P")):
                source = _value(row, cols[0]).strip()
                if not source:
                    continue
                vals = [_value(row, c) for c in cols]
                status = "DEGRADED_SOURCE" if any(v.strip() in ERROR_MARKERS for v in vals) else "SOURCE_OK"
                self.translators[source.casefold()] = {
                    "source_domain": source,
                    "base_vector": vals[1],
                    "self_attention": vals[2],
                    "kex_output": vals[3],
                    "source_row": str(n),
                    "source_status": status,
                }

        run_rows = _cell_rows(self.raw.get("IL-LLM Runtime Engine", []))
        for n, row in sorted(run_rows.items()):
            if n == 1:
                continue
            register = _value(row, "A").strip()
            if register:
                self.runtime_registers[register] = {
                    "value": _value(row, "B"), "context_rotation": _value(row, "C"),
                    "emergent_definition": _value(row, "D"), "dna_function_map": _value(row, "E"),
                    "zero_veto_validation": _value(row, "F"), "kex_output": _value(row, "G"),
                    "source_row": str(n),
                }

    @property
    def workbook_sha256(self) -> str:
        return sha256_hex(self.path.read_bytes())

    def summary(self) -> dict[str, Any]:
        degraded = sum(1 for r in self.lexicon.values() if r.source_status != "SOURCE_OK")
        return {
            "schema": "il-llm.recovered-adapter.v1",
            "source_path": str(self.path),
            "source_sha256": self.workbook_sha256,
            "lexicon_entries": len(self.lexicon),
            "degraded_lexicon_entries": degraded,
            "recovered_router_entries": len(self.recovered_router),
            "translator_domains": len(self.translators),
            "runtime_registers": len(self.runtime_registers),
            "claim_boundary": "read-only adapter over recovered workbook surfaces; not the full IL-LLM runtime",
        }

    def resolve(self, symbol: str, *, require_clean: bool = False) -> SemanticRecord:
        key = symbol.strip().casefold()
        if not key:
            raise SemanticResolutionError("EMPTY_SYMBOL")
        rec = self.lexicon.get(key)
        if rec is None:
            raise SemanticResolutionError(f"UNRESOLVED_SYMBOL:{symbol}")
        if require_clean and rec.source_status != "SOURCE_OK":
            raise SemanticResolutionError(f"DEGRADED_SOURCE:{symbol}:{rec.source_sheet}!{rec.source_row}")
        return rec

    def route_for(self, rec: SemanticRecord) -> dict[str, Any]:
        recovered = self.recovered_router.get(rec.entity.casefold())
        tx = self.translators.get("human language (english)")
        route = {
            "semantic_owner": "IL-LLM",
            "kex_translation_route": tx.get("kex_output") if tx else None,
            "translator_source": tx,
            "routing_hash": None,
            "routing_hash_source": None,
        }
        if recovered and recovered.get("routing_hash") and recovered["routing_hash"] not in ERROR_MARKERS:
            route["routing_hash"] = recovered["routing_hash"]
            route["routing_hash_source"] = "BRAINK_LEXICON_ROUTER_RECOVERED"
        elif rec.routing_hash and rec.routing_hash not in ERROR_MARKERS:
            route["routing_hash"] = rec.routing_hash
            route["routing_hash_source"] = rec.source_sheet
        return route


@dataclass(frozen=True)
class KEXConcept:
    symbol: str
    meaning: dict[str, Any]
    kex_route: str
    coordinate: str
    coordinate_kind: str
    source_locator: str
    source_status: str
    semantic_digest: str


class KEXSemanticTranslator:
    def __init__(self, adapter: ResidentILLMAdapter):
        self.adapter = adapter

    def translate(self, symbol: str, *, require_clean: bool = False) -> KEXConcept:
        rec = self.adapter.resolve(symbol, require_clean=require_clean)
        meaning = rec.semantic_payload()
        digest = sha256_hex(canonical_json_bytes(meaning))
        route = self.adapter.route_for(rec)
        if route.get("routing_hash"):
            coordinate = str(route["routing_hash"])
            kind = "RESIDENT_ROUTING_HASH"
        else:
            # Fallback identity is explicitly adapter-local, not promoted as a resident KEX routing hash.
            slug = re.sub(r"[^a-z0-9]+", "-", rec.entity.casefold()).strip("-") or "symbol"
            coordinate = f"semantic://il-llm/{slug}/{digest[:16]}"
            kind = "ADAPTER_LOCAL_SEMANTIC_COORDINATE"
        return KEXConcept(
            symbol=rec.entity,
            meaning=meaning,
            kex_route=(route.get("kex_translation_route") or "UNRESOLVED_KEX_TRANSLATOR"),
            coordinate=coordinate,
            coordinate_kind=kind,
            source_locator=f"{rec.source_sheet}!row:{rec.source_row}",
            source_status=rec.source_status,
            semantic_digest=digest,
        )

    def translate_many(self, symbols: Iterable[str], *, require_clean: bool = False) -> list[KEXConcept]:
        return [self.translate(x, require_clean=require_clean) for x in symbols]


class HTMLConceptProjector:
    @staticmethod
    def project(concepts: list[KEXConcept], title: str = "KEX / IL-LLM Concept Projection") -> str:
        cards=[]
        for c in concepts:
            meaning=c.meaning
            attrs = {
                "data-il-llm-symbol": c.symbol,
                "data-kex-coordinate": c.coordinate,
                "data-kex-route": c.kex_route,
                "data-semantic-digest": c.semantic_digest,
                "data-source-status": c.source_status,
            }
            attr_text=" ".join(f'{k}="{html.escape(str(v), quote=True)}"' for k,v in attrs.items())
            fields=[]
            for label,key in [
                ("Dictionary meaning","dictionary_meaning"),("Thesaurus","thesaurus"),("Concept","concept"),
                ("Core meaning","core_meaning"),("Environment","environment"),("Observer perspective","observer_perspective"),
                ("Composition","composition"),("Effect","effect")]:
                v=str(meaning.get(key) or "")
                if v:
                    fields.append(f'<dt>{html.escape(label)}</dt><dd>{html.escape(v)}</dd>')
            cards.append(
                f'<article class="kex-concept" {attr_text}>'
                f'<h2>{html.escape(c.symbol)}</h2><p class="coordinate">{html.escape(c.coordinate)}</p>'
                f'<dl>{"".join(fields)}</dl><footer>{html.escape(c.source_locator)} · {html.escape(c.source_status)}</footer></article>'
            )
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title>'
            '<style>body{font-family:system-ui;max-width:1000px;margin:40px auto;padding:0 20px;line-height:1.5}'
            '.kex-concept{border:1px solid #bbb;border-radius:14px;padding:18px;margin:16px 0}.coordinate{font-family:monospace;overflow-wrap:anywhere}'
            'dt{font-weight:700;margin-top:8px}dd{margin-left:0}footer{margin-top:16px;font-size:.85em;opacity:.7}</style>'
            f'</head><body><h1>{html.escape(title)}</h1><main>{"".join(cards)}</main></body></html>'
        )


class ABCodec:
    """Canonical A/B run codec.

    A1..A9 encode runs of binary 1; B1..B9 encode runs of binary 0.
    Long runs are split into maximal 9-sized chunks followed by one remainder.
    This is a reversible project codec, not a claim of compression or a standard codec.
    """
    TOKEN_RE = re.compile(r"(?:[AB][1-9])+")

    @classmethod
    def encode_bits(cls, bits: str) -> str:
        if bits == "":
            return ""
        if any(ch not in "01" for ch in bits):
            raise BoundaryError("NON_BINARY_INPUT")
        out=[]; i=0
        while i < len(bits):
            bit=bits[i]; j=i+1
            while j<len(bits) and bits[j]==bit: j+=1
            run=j-i; prefix="A" if bit=="1" else "B"
            while run>9:
                out.append(prefix+"9"); run-=9
            if run:
                out.append(prefix+str(run))
            i=j
        return "".join(out)

    @classmethod
    def decode_bits(cls, tokens: str, *, require_canonical: bool = True) -> str:
        if tokens == "": return ""
        if not cls.TOKEN_RE.fullmatch(tokens):
            raise BoundaryError("INVALID_AB_TOKEN_STREAM")
        bits=[]
        for p,n in re.findall(r"([AB])([1-9])",tokens):
            bits.append(("1" if p=="A" else "0")*int(n))
        out="".join(bits)
        if require_canonical and cls.encode_bits(out)!=tokens:
            raise BoundaryError("NON_CANONICAL_AB_TOKEN_STREAM")
        return out

    @classmethod
    def bytes_to_tokens(cls, data: bytes) -> str:
        bits="".join(f"{b:08b}" for b in data)
        return cls.encode_bits(bits)

    @classmethod
    def tokens_to_bytes(cls, tokens: str) -> bytes:
        bits=cls.decode_bits(tokens)
        if len(bits)%8:
            raise BoundaryError("BIT_LENGTH_NOT_BYTE_ALIGNED")
        return bytes(int(bits[i:i+8],2) for i in range(0,len(bits),8))

    @staticmethod
    def pack_tokens(tokens: str) -> bytes:
        if tokens == "": return b""
        if not ABCodec.TOKEN_RE.fullmatch(tokens): raise BoundaryError("INVALID_AB_TOKEN_STREAM")
        out=bytearray()
        for p,n in re.findall(r"([AB])([1-9])",tokens):
            count=int(n)
            out.append((0x80 if p=="A" else 0x00)|count)
        return bytes(out)

    @staticmethod
    def unpack_tokens(packed: bytes) -> str:
        out=[]
        for b in packed:
            # Bits 4..6 are reserved and must be zero; low nibble count is 1..9.
            if b & 0x70: raise BoundaryError("AB_RESERVED_BITS_SET")
            count=b & 0x0F
            if count<1 or count>9: raise BoundaryError("AB_COUNT_OUT_OF_RANGE")
            out.append(("A" if b & 0x80 else "B")+str(count))
        tokens="".join(out)
        # This also rejects alternate chunking such as A5A4 for a run of 9.
        ABCodec.decode_bits(tokens, require_canonical=True)
        return tokens


@dataclass(frozen=True)
class BoundaryReceipt:
    schema: str
    encoding: str
    source_text_sha256: str
    source_bytes_sha256: str
    source_bytes: int
    ab_token_chars: int
    ab_run_tokens: int
    wire_bytes: int
    token_char_ratio_to_source_bytes: float
    wire_ratio_to_source_bytes: float
    roundtrip_equal: bool


class BinaryBoundaryAdapter:
    HEADER = struct.Struct(">4sBQI32s")  # magic, version, payload_len, token_count, payload sha256

    @classmethod
    def encode_bytes(cls, payload: bytes) -> tuple[bytes, str, BoundaryReceipt]:
        tokens=ABCodec.bytes_to_tokens(payload)
        packed=ABCodec.pack_tokens(tokens)
        digest=hashlib.sha256(payload).digest()
        wire=cls.HEADER.pack(AB_MAGIC,AB_VERSION,len(payload),len(packed),digest)+packed
        recovered,_=cls.decode_bytes(wire)
        denom=max(1,len(payload))
        receipt=BoundaryReceipt(
            schema=SCHEMA, encoding="KAB1:A=1-run,B=0-run,count=1..9",
            source_text_sha256="", source_bytes_sha256=digest.hex(), source_bytes=len(payload),
            ab_token_chars=len(tokens), ab_run_tokens=len(packed), wire_bytes=len(wire),
            token_char_ratio_to_source_bytes=round(len(tokens)/denom,6),
            wire_ratio_to_source_bytes=round(len(wire)/denom,6),
            roundtrip_equal=(recovered==payload),
        )
        return wire,tokens,receipt

    @classmethod
    def decode_bytes(cls, wire: bytes) -> tuple[bytes, dict[str, Any]]:
        if len(wire)<cls.HEADER.size: raise BoundaryError("TRUNCATED_KAB1_HEADER")
        magic,version,payload_len,token_count,digest=cls.HEADER.unpack(wire[:cls.HEADER.size])
        if magic!=AB_MAGIC: raise BoundaryError("BAD_KAB1_MAGIC")
        if version!=AB_VERSION: raise BoundaryError("UNSUPPORTED_KAB1_VERSION")
        packed=wire[cls.HEADER.size:]
        if len(packed)!=token_count: raise BoundaryError("KAB1_TOKEN_COUNT_MISMATCH")
        tokens=ABCodec.unpack_tokens(packed)
        payload=ABCodec.tokens_to_bytes(tokens)
        if len(payload)!=payload_len: raise BoundaryError("KAB1_PAYLOAD_LENGTH_MISMATCH")
        actual=hashlib.sha256(payload).digest()
        if actual!=digest: raise BoundaryError("KAB1_PAYLOAD_DIGEST_MISMATCH")
        return payload,{"payload_len":payload_len,"token_count":token_count,"sha256":actual.hex(),"tokens":tokens}

    @classmethod
    def encode_text(cls, text: str) -> tuple[bytes,str,BoundaryReceipt]:
        payload=text.encode("utf-8")
        wire,tokens,receipt=cls.encode_bytes(payload)
        receipt=BoundaryReceipt(**{**asdict(receipt),"source_text_sha256":sha256_hex(text.encode("utf-8"))})
        return wire,tokens,receipt

    @classmethod
    def decode_text(cls, wire: bytes) -> tuple[str,dict[str,Any]]:
        payload,meta=cls.decode_bytes(wire)
        try: text=payload.decode("utf-8",errors="strict")
        except UnicodeDecodeError as exc: raise BoundaryError("INVALID_UTF8_PAYLOAD") from exc
        return text,meta


class SymbolicBoundaryPipeline:
    def __init__(self, translator: KEXSemanticTranslator):
        self.translator=translator

    def execute(self, symbols: list[str], *, require_clean: bool=False) -> dict[str,Any]:
        concepts=self.translator.translate_many(symbols,require_clean=require_clean)
        html_text=HTMLConceptProjector.project(concepts)
        wire,tokens,receipt=BinaryBoundaryAdapter.encode_text(html_text)
        readback,meta=BinaryBoundaryAdapter.decode_text(wire)
        if readback!=html_text: raise BoundaryError("HTML_ROUNDTRIP_MISMATCH")
        return {
            "schema":SCHEMA,
            "concepts":[asdict(c) for c in concepts],
            "html":html_text,
            "html_sha256":sha256_hex(html_text.encode("utf-8")),
            "ab_tokens":tokens,
            "wire":wire,
            "boundary_receipt":asdict(receipt),
            "readback_meta":meta,
            "roundtrip_equal":True,
        }

class AdaptiveBinaryBoundaryAdapter:
    """KEX boundary selector: use A/B only when it beats a raw integrity envelope.

    The selector is evidence-driven and deterministic. It preserves the user's A/B
    codec as a boundary option without pretending that run-length coding is superior
    for arbitrary byte distributions.
    """
    RAW_MAGIC=b'KRW1'
    RAW_HEADER=struct.Struct('>4sBQ32s')  # magic, version, payload_len, sha256

    @classmethod
    def _raw_encode(cls,payload:bytes)->bytes:
        return cls.RAW_HEADER.pack(cls.RAW_MAGIC,1,len(payload),hashlib.sha256(payload).digest())+payload

    @classmethod
    def _raw_decode(cls,wire:bytes)->bytes:
        if len(wire)<cls.RAW_HEADER.size: raise BoundaryError('TRUNCATED_KRW1_HEADER')
        magic,version,n,digest=cls.RAW_HEADER.unpack(wire[:cls.RAW_HEADER.size])
        if magic!=cls.RAW_MAGIC: raise BoundaryError('BAD_KRW1_MAGIC')
        if version!=1: raise BoundaryError('UNSUPPORTED_KRW1_VERSION')
        payload=wire[cls.RAW_HEADER.size:]
        if len(payload)!=n: raise BoundaryError('KRW1_PAYLOAD_LENGTH_MISMATCH')
        if hashlib.sha256(payload).digest()!=digest: raise BoundaryError('KRW1_PAYLOAD_DIGEST_MISMATCH')
        return payload

    @classmethod
    def encode_bytes(cls,payload:bytes)->tuple[bytes,dict[str,Any]]:
        kab,tokens,kab_receipt=BinaryBoundaryAdapter.encode_bytes(payload)
        raw=cls._raw_encode(payload)
        if len(kab)<len(raw):
            return kab,{'mode':'KAB1','wire_bytes':len(kab),'raw_candidate_bytes':len(raw),'kab_candidate_bytes':len(kab),'ab_tokens_sha256':sha256_hex(tokens.encode('ascii')),'ab_token_chars':len(tokens),'kab_receipt':asdict(kab_receipt)}
        return raw,{'mode':'KRW1','wire_bytes':len(raw),'raw_candidate_bytes':len(raw),'kab_candidate_bytes':len(kab),'ab_tokens_sha256':sha256_hex(tokens.encode('ascii')),'ab_token_chars':len(tokens),'kab_receipt':asdict(kab_receipt)}

    @classmethod
    def decode_bytes(cls,wire:bytes)->tuple[bytes,dict[str,Any]]:
        if wire[:4]==AB_MAGIC:
            payload,meta=BinaryBoundaryAdapter.decode_bytes(wire); return payload,{'mode':'KAB1',**meta}
        if wire[:4]==cls.RAW_MAGIC:
            payload=cls._raw_decode(wire); return payload,{'mode':'KRW1','payload_len':len(payload),'sha256':sha256_hex(payload)}
        raise BoundaryError('UNKNOWN_BOUNDARY_MAGIC')

    @classmethod
    def encode_text(cls,text:str)->tuple[bytes,dict[str,Any]]:
        wire,meta=cls.encode_bytes(text.encode('utf-8'))
        return wire,{**meta,'text_sha256':sha256_hex(text.encode('utf-8'))}

    @classmethod
    def decode_text(cls,wire:bytes)->tuple[str,dict[str,Any]]:
        payload,meta=cls.decode_bytes(wire)
        try: return payload.decode('utf-8',errors='strict'),meta
        except UnicodeDecodeError as exc: raise BoundaryError('INVALID_UTF8_PAYLOAD') from exc