from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import hashlib
import json
import re


class ChemicalLinguisticError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


ELEMENTS = [
("H","hydrogen"),("He","helium"),("Li","lithium"),("Be","beryllium"),("B","boron"),("C","carbon"),
("N","nitrogen"),("O","oxygen"),("F","fluorine"),("Ne","neon"),("Na","sodium"),("Mg","magnesium"),
("Al","aluminium"),("Si","silicon"),("P","phosphorus"),("S","sulfur"),("Cl","chlorine"),("Ar","argon"),
("K","potassium"),("Ca","calcium"),("Sc","scandium"),("Ti","titanium"),("V","vanadium"),("Cr","chromium"),
("Mn","manganese"),("Fe","iron"),("Co","cobalt"),("Ni","nickel"),("Cu","copper"),("Zn","zinc"),
("Ga","gallium"),("Ge","germanium"),("As","arsenic"),("Se","selenium"),("Br","bromine"),("Kr","krypton"),
("Rb","rubidium"),("Sr","strontium"),("Y","yttrium"),("Zr","zirconium"),("Nb","niobium"),("Mo","molybdenum"),
("Tc","technetium"),("Ru","ruthenium"),("Rh","rhodium"),("Pd","palladium"),("Ag","silver"),("Cd","cadmium"),
("In","indium"),("Sn","tin"),("Sb","antimony"),("Te","tellurium"),("I","iodine"),("Xe","xenon"),
("Cs","caesium"),("Ba","barium"),("La","lanthanum"),("Ce","cerium"),("Pr","praseodymium"),("Nd","neodymium"),
("Pm","promethium"),("Sm","samarium"),("Eu","europium"),("Gd","gadolinium"),("Tb","terbium"),("Dy","dysprosium"),
("Ho","holmium"),("Er","erbium"),("Tm","thulium"),("Yb","ytterbium"),("Lu","lutetium"),("Hf","hafnium"),
("Ta","tantalum"),("W","tungsten"),("Re","rhenium"),("Os","osmium"),("Ir","iridium"),("Pt","platinum"),
("Au","gold"),("Hg","mercury"),("Tl","thallium"),("Pb","lead"),("Bi","bismuth"),("Po","polonium"),
("At","astatine"),("Rn","radon"),("Fr","francium"),("Ra","radium"),("Ac","actinium"),("Th","thorium"),
("Pa","protactinium"),("U","uranium"),("Np","neptunium"),("Pu","plutonium"),("Am","americium"),("Cm","curium"),
("Bk","berkelium"),("Cf","californium"),("Es","einsteinium"),("Fm","fermium"),("Md","mendelevium"),
("No","nobelium"),("Lr","lawrencium"),("Rf","rutherfordium"),("Db","dubnium"),("Sg","seaborgium"),
("Bh","bohrium"),("Hs","hassium"),("Mt","meitnerium"),("Ds","darmstadtium"),("Rg","roentgenium"),
("Cn","copernicium"),("Nh","nihonium"),("Fl","flerovium"),("Mc","moscovium"),("Lv","livermorium"),
("Ts","tennessine"),("Og","oganesson")
]
_BY_NUMBER={i+1:{"atomic_number":i+1,"symbol":s,"canonical_name_en":n} for i,(s,n) in enumerate(ELEMENTS)}
_BY_NAME={v["canonical_name_en"]:v for v in _BY_NUMBER.values()}


@dataclass(frozen=True)
class NumericAddress:
    raw_value: float
    addressing_mode: str
    quantisation_rule: str
    atomic_number: int


@dataclass(frozen=True)
class ScientificAssertion:
    subject_atomic_number: int
    property_id: str
    value: Any
    unit: str | None
    conditions: str | None
    source: str
    observed_at: str | None = None


MEMORY_OPERATORS={
    "+1":"POSITIVE_REINFORCEMENT",
    "-1":"NEGATIVE_REINFORCEMENT",
    ".1":"LOW_MAGNITUDE",
    "/1":"NORMALISATION",
    "+M1":"META_POSITIVE_REINFORCEMENT",
    "-M1":"META_NEGATIVE_REINFORCEMENT",
}


class ElementAddressing:
    @staticmethod
    def resolve(raw_value: float, mode: str="atomic_number_direct") -> NumericAddress:
        if mode=="atomic_number_direct":
            if int(raw_value)!=raw_value:
                raise ChemicalLinguisticError("DIRECT_ADDRESS_REQUIRES_INTEGER")
            atomic=int(raw_value)
            rule="identity(integer)"
        elif mode=="bucket_zero_based":
            atomic=(int(raw_value//1)%118)+1
            rule="(floor(value) % 118) + 1"
        else:
            raise ChemicalLinguisticError(f"UNKNOWN_ADDRESSING_MODE:{mode}")
        if atomic not in _BY_NUMBER:
            raise ChemicalLinguisticError(f"ATOMIC_NUMBER_OUT_OF_RANGE:{atomic}")
        return NumericAddress(float(raw_value),mode,rule,atomic)

    @staticmethod
    def identity(address: NumericAddress) -> dict[str,Any]:
        return dict(_BY_NUMBER[address.atomic_number])


class ChemicalSemanticGraph:
    @staticmethod
    def build(
        address: NumericAddress,
        assertions: list[ScientificAssertion] | None=None,
        memory_operators: list[str] | None=None,
        relations: list[dict[str,Any]] | None=None,
    ) -> dict[str,Any]:
        assertions=assertions or []
        for a in assertions:
            if a.subject_atomic_number!=address.atomic_number:
                raise ChemicalLinguisticError("ASSERTION_SUBJECT_MISMATCH")
            if not a.source:
                raise ChemicalLinguisticError("ASSERTION_SOURCE_REQUIRED")
        mem=[]
        for op in memory_operators or []:
            semantic=MEMORY_OPERATORS.get(op)
            if semantic is None:
                raise ChemicalLinguisticError(f"UNKNOWN_MEMORY_OPERATOR:{op}")
            mem.append({"operator":op,"semantic_operation":semantic})
        graph={
            "schema":"braink.chemical-semantic-graph.r1/v1",
            "numeric_address":asdict(address),
            "element_identity":ElementAddressing.identity(address),
            "scientific_assertions":[asdict(a) for a in assertions],
            "memory_operations":mem,
            "relations":relations or [],
        }
        graph["semantic_root"]=sha256(graph)
        return graph


class ControlledEnglishCodec:
    ADDRESS_RE=re.compile(
        r'^Address raw=(?P<raw>.+?) \\| mode=(?P<mode>.+?) \\| rule=(?P<rule>.+?) \\| atomic_number=(?P<atomic>\\d+)\\.re.compile(r"^Element (?P<num>\d+) is (?P<name>[a-z]+) \((?P<symbol>[A-Z][a-z]?)\)\.$")
    PROPERTY_RE=re.compile(
        r"^(?P<name>[A-Z][a-z]+) has (?P<property>[a-z0-9_.:-]+) = "
        r"(?P<value>.*?)(?: \| unit=(?P<unit>.*?))?(?: \| conditions=(?P<conditions>.*?))?"
        r" \| source=(?P<source>.+)\.$"
    )
    RELATION_RE=re.compile(r"^(?P<subject>[A-Z][a-z]+) bonds with (?P<object>[a-z]+) \| source=(?P<source>.+)\.$")

    @staticmethod
    def display(name:str)->str:
        return name[:1].upper()+name[1:]

    @classmethod
    def lexicalise(cls,graph:dict[str,Any])->dict[str,Any]:
        e=graph["element_identity"]
        a=graph["numeric_address"]
        sentences=[
            f'Address raw={canonical_json(a["raw_value"])} | mode={canonical_json(a["addressing_mode"])}'
            f' | rule={canonical_json(a["quantisation_rule"])} | atomic_number={a["atomic_number"]}.',
            f'Element {e["atomic_number"]} is {e["canonical_name_en"]} ({e["symbol"]}).'
        ]
        provenance=[
            {
                "sentence_index":0,
                "semantic_object":"numeric_address",
                "source":"braink://linguistics/chemical/addressing-rule",
            },
            {
                "sentence_index":1,
                "semantic_object":"element_identity",
                "source":f'element/{e["atomic_number"]}/name/iupac/en',
            },
        ]
        for mem in graph.get("memory_operations",[]):
            sentences.append(
                f'Memory operator {canonical_json(mem["operator"])}'
                f' | semantic_operation={mem["semantic_operation"]}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"memory_operation",
                "source":"braink://linguistics/chemical/memory-operator-registry",
            })
        for a in graph.get("scientific_assertions",[]):
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} has {a["property_id"]}'
                f' | value={canonical_json(a["value"])}'
                f' | unit={canonical_json(a.get("unit"))}'
                f' | conditions={canonical_json(a.get("conditions"))}'
                f' | observed_at={canonical_json(a.get("observed_at"))}'
                f' | source={canonical_json(a["source"])}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"scientific_assertion",
                "property_id":a["property_id"],
                "source":a["source"],
            })
        for rel in graph.get("relations",[]):
            if rel.get("type")!="BONDS_WITH":
                continue
            obj=_BY_NUMBER.get(int(rel["object_atomic_number"]))
            if not obj:
                raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
            source=rel.get("source")
            if not source:
                raise ChemicalLinguisticError("RELATION_SOURCE_REQUIRED")
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} bonds with {obj["canonical_name_en"]} | source={canonical_json(source)}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"relation",
                "relation":"BONDS_WITH",
                "source":source,
            })
        return {
            "schema":"braink.controlled-english.r1/v1",
            "sentences":sentences,
            "text":" ".join(sentences),
            "provenance":provenance,
            "source_semantic_root":graph["semantic_root"],
        }

    @classmethod
    def parse(cls,controlled:dict[str,Any])->dict[str,Any]:
        sentences=controlled.get("sentences")
        if not isinstance(sentences,list) or len(sentences)<2:
            raise ChemicalLinguisticError("CONTROLLED_SENTENCES_REQUIRED")

        am=cls.ADDRESS_RE.fullmatch(sentences[0])
        if not am:
            raise ChemicalLinguisticError("ADDRESS_SENTENCE_NOT_PARSEABLE")
        try:
            raw_value=json.loads(am.group("raw"))
            addressing_mode=json.loads(am.group("mode"))
            quantisation_rule=json.loads(am.group("rule"))
        except json.JSONDecodeError as exc:
            raise ChemicalLinguisticError("ADDRESS_TYPED_FIELD_DECODE_FAILED") from exc
        address=NumericAddress(
            raw_value=float(raw_value),
            addressing_mode=str(addressing_mode),
            quantisation_rule=str(quantisation_rule),
            atomic_number=int(am.group("atomic")),
        )
        expected_address=ElementAddressing.resolve(address.raw_value,address.addressing_mode)
        if expected_address!=address:
            raise ChemicalLinguisticError("ADDRESS_RULE_READBACK_MISMATCH")

        m=cls.IDENTITY_RE.fullmatch(sentences[1])
        if not m:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_NOT_PARSEABLE")
        atomic=int(m.group("num"))
        expected=_BY_NUMBER.get(atomic)
        if expected is None:
            raise ChemicalLinguisticError("PARSED_ATOMIC_NUMBER_UNKNOWN")
        if m.group("name")!=expected["canonical_name_en"] or m.group("symbol")!=expected["symbol"]:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_CONTRADICTS_ELEMENT_TABLE")
        if atomic!=address.atomic_number:
            raise ChemicalLinguisticError("PARSED_IDENTITY_ADDRESS_MISMATCH")

        assertions=[]
        relations=[]
        memory_operations=[]
        for sentence in sentences[2:]:
            mm=cls.MEMORY_RE.fullmatch(sentence)
            if mm:
                try:
                    operator=json.loads(mm.group("operator"))
                except json.JSONDecodeError as exc:
                    raise ChemicalLinguisticError("MEMORY_OPERATOR_DECODE_FAILED") from exc
                semantic=MEMORY_OPERATORS.get(operator)
                if semantic is None or semantic!=mm.group("semantic"):
                    raise ChemicalLinguisticError("MEMORY_OPERATOR_SEMANTIC_MISMATCH")
                memory_operations.append({"operator":operator,"semantic_operation":semantic})
                continue
            pm=cls.PROPERTY_RE.fullmatch(sentence)
            if pm:
                if pm.group("name").casefold()!=expected["canonical_name_en"]:
                    raise ChemicalLinguisticError("PROPERTY_SUBJECT_MISMATCH")
                try:
                    value=json.loads(pm.group("value"))
                    unit=json.loads(pm.group("unit"))
                    conditions=json.loads(pm.group("conditions"))
                    observed_at=json.loads(pm.group("observed_at"))
                    source=json.loads(pm.group("source"))
                except json.JSONDecodeError as exc:
                    raise ChemicalLinguisticError("PROPERTY_TYPED_FIELD_DECODE_FAILED") from exc
                assertions.append({
                    "subject_atomic_number":atomic,
                    "property_id":pm.group("property"),
                    "value":value,
                    "unit":unit,
                    "conditions":conditions,
                    "source":source,
                    "observed_at":observed_at,
                })
                continue
            rm=cls.RELATION_RE.fullmatch(sentence)
            if rm:
                obj=_BY_NAME.get(rm.group("object"))
                if obj is None:
                    raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
                relations.append({
                    "type":"BONDS_WITH",
                    "subject_atomic_number":atomic,
                    "object_atomic_number":obj["atomic_number"],
                    "source":json.loads(rm.group("source")),
                })
                continue
            raise ChemicalLinguisticError(f"UNSUPPORTED_CONTROLLED_SENTENCE:{sentence}")

        graph={
            "schema":"braink.chemical-semantic-graph.r1/v1",
            "numeric_address":asdict(address),
            "element_identity":dict(expected),
            "scientific_assertions":assertions,
            "memory_operations":memory_operations,
            "relations":relations,
        }
        graph["semantic_root"]=sha256(graph)
        return graph


class ChemicalLinguisticEngine:
    def execute(
        self,
        raw_value: float,
        addressing_mode: str="atomic_number_direct",
        assertions: list[dict[str,Any]] | None=None,
        memory_operators: list[str] | None=None,
        relations: list[dict[str,Any]] | None=None,
    )->dict[str,Any]:
        address=ElementAddressing.resolve(raw_value,addressing_mode)
        assertion_objects=[]
        for raw in assertions or []:
            assertion_objects.append(ScientificAssertion(
                subject_atomic_number=int(raw.get("subject_atomic_number",address.atomic_number)),
                property_id=str(raw["property_id"]),
                value=raw["value"],
                unit=raw.get("unit"),
                conditions=raw.get("conditions"),
                source=str(raw["source"]),
                observed_at=raw.get("observed_at"),
            ))
        graph=ChemicalSemanticGraph.build(address,assertion_objects,memory_operators,relations)
        controlled=ControlledEnglishCodec.lexicalise(graph)
        parsed=ControlledEnglishCodec.parse(controlled)
        equivalent=(parsed["semantic_root"]==graph["semantic_root"])
        return {
            "schema":"braink.chemical-linguistic-engine.r1/v1",
            "address":asdict(address),
            "element_identity":graph["element_identity"],
            "semantic_graph":graph,
            "controlled_english":controlled,
            "readback_graph":parsed,
            "proof":{
                "equivalence_relation":"canonical semantic graph equality",
                "source_root":graph["semantic_root"],
                "readback_root":parsed["semantic_root"],
                "roundtrip_equivalent":equivalent,
                "controlled_generation":True,
                "provenance_complete":all(bool(p.get("source")) for p in controlled["provenance"]),
            },
        }


def self_test()->dict[str,Any]:
    engine=ChemicalLinguisticEngine()
    direct=engine.execute(
        8,
        "atomic_number_direct",
        assertions=[{
            "property_id":"phase",
            "value":"gas",
            "unit":None,
            "conditions":"specified conditions",
            "source":"test://phase/oxygen",
        }],
        memory_operators=["+1","/1"],
        relations=[{
            "type":"BONDS_WITH",
            "subject_atomic_number":8,
            "object_atomic_number":1,
            "source":"test://relation/oxygen-hydrogen",
        }],
    )
    bucket=engine.execute(7,"bucket_zero_based")
    checks={
        "direct_8_is_oxygen":direct["element_identity"]["symbol"]=="O",
        "bucket_7_is_oxygen":bucket["element_identity"]["symbol"]=="O",
        "addressing_modes_distinct":direct["address"]["addressing_mode"]!=bucket["address"]["addressing_mode"],
        "memory_operator_is_semantic_not_word":direct["semantic_graph"]["memory_operations"][0]["semantic_operation"]=="POSITIVE_REINFORCEMENT",
        "roundtrip_equivalent":direct["proof"]["roundtrip_equivalent"] is True,
        "provenance_complete":direct["proof"]["provenance_complete"] is True,
    }
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks}


if __name__=="__main__":
    print(json.dumps(self_test(),indent=2))

    )
    MEMORY_RE=re.compile(
        r'^Memory operator (?P<operator>.+?) \\| semantic_operation=(?P<semantic>[A-Z_]+)\\.re.compile(r"^Element (?P<num>\d+) is (?P<name>[a-z]+) \((?P<symbol>[A-Z][a-z]?)\)\.$")
    PROPERTY_RE=re.compile(
        r"^(?P<name>[A-Z][a-z]+) has (?P<property>[a-z0-9_.:-]+) = "
        r"(?P<value>.*?)(?: \| unit=(?P<unit>.*?))?(?: \| conditions=(?P<conditions>.*?))?"
        r" \| source=(?P<source>.+)\.$"
    )
    RELATION_RE=re.compile(r"^(?P<subject>[A-Z][a-z]+) bonds with (?P<object>[a-z]+) \| source=(?P<source>.+)\.$")

    @staticmethod
    def display(name:str)->str:
        return name[:1].upper()+name[1:]

    @classmethod
    def lexicalise(cls,graph:dict[str,Any])->dict[str,Any]:
        e=graph["element_identity"]
        sentences=[f'Element {e["atomic_number"]} is {e["canonical_name_en"]} ({e["symbol"]}).']
        provenance=[{
            "sentence_index":0,
            "semantic_object":"element_identity",
            "source":f'element/{e["atomic_number"]}/name/iupac/en',
        }]
        for a in graph.get("scientific_assertions",[]):
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} has {a["property_id"]}'
                f' | value={canonical_json(a["value"])}'
                f' | unit={canonical_json(a.get("unit"))}'
                f' | conditions={canonical_json(a.get("conditions"))}'
                f' | source={canonical_json(a["source"])}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"scientific_assertion",
                "property_id":a["property_id"],
                "source":a["source"],
            })
        for rel in graph.get("relations",[]):
            if rel.get("type")!="BONDS_WITH":
                continue
            obj=_BY_NUMBER.get(int(rel["object_atomic_number"]))
            if not obj:
                raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
            source=rel.get("source")
            if not source:
                raise ChemicalLinguisticError("RELATION_SOURCE_REQUIRED")
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} bonds with {obj["canonical_name_en"]} | source={source}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"relation",
                "relation":"BONDS_WITH",
                "source":source,
            })
        return {
            "schema":"braink.controlled-english.r1/v1",
            "sentences":sentences,
            "text":" ".join(sentences),
            "provenance":provenance,
            "source_semantic_root":graph["semantic_root"],
        }

    @classmethod
    def parse(cls,controlled:dict[str,Any],address:NumericAddress,memory_operations:list[dict[str,Any]])->dict[str,Any]:
        sentences=controlled.get("sentences")
        if not isinstance(sentences,list) or not sentences:
            raise ChemicalLinguisticError("CONTROLLED_SENTENCES_REQUIRED")
        m=cls.IDENTITY_RE.fullmatch(sentences[0])
        if not m:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_NOT_PARSEABLE")
        atomic=int(m.group("num"))
        expected=_BY_NUMBER.get(atomic)
        if expected is None:
            raise ChemicalLinguisticError("PARSED_ATOMIC_NUMBER_UNKNOWN")
        if m.group("name")!=expected["canonical_name_en"] or m.group("symbol")!=expected["symbol"]:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_CONTRADICTS_ELEMENT_TABLE")
        if atomic!=address.atomic_number:
            raise ChemicalLinguisticError("PARSED_IDENTITY_ADDRESS_MISMATCH")

        assertions=[]
        relations=[]
        for sentence in sentences[1:]:
            pm=cls.PROPERTY_RE.fullmatch(sentence)
            if pm:
                if pm.group("name").casefold()!=expected["canonical_name_en"]:
                    raise ChemicalLinguisticError("PROPERTY_SUBJECT_MISMATCH")
                try:
                    value=json.loads(pm.group("value"))
                    unit=json.loads(pm.group("unit"))
                    conditions=json.loads(pm.group("conditions"))
                    source=json.loads(pm.group("source"))
                except json.JSONDecodeError as exc:
                    raise ChemicalLinguisticError("PROPERTY_TYPED_FIELD_DECODE_FAILED") from exc
                assertions.append({
                    "subject_atomic_number":atomic,
                    "property_id":pm.group("property"),
                    "value":value,
                    "unit":unit,
                    "conditions":conditions,
                    "source":source,
                    "observed_at":None,
                })
                continue
            rm=cls.RELATION_RE.fullmatch(sentence)
            if rm:
                obj=_BY_NAME.get(rm.group("object"))
                if obj is None:
                    raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
                relations.append({
                    "type":"BONDS_WITH",
                    "subject_atomic_number":atomic,
                    "object_atomic_number":obj["atomic_number"],
                    "source":rm.group("source"),
                })
                continue
            raise ChemicalLinguisticError(f"UNSUPPORTED_CONTROLLED_SENTENCE:{sentence}")

        graph={
            "schema":"braink.chemical-semantic-graph.r1/v1",
            "numeric_address":asdict(address),
            "element_identity":dict(expected),
            "scientific_assertions":assertions,
            "memory_operations":memory_operations,
            "relations":relations,
        }
        graph["semantic_root"]=sha256(graph)
        return graph


class ChemicalLinguisticEngine:
    def execute(
        self,
        raw_value: float,
        addressing_mode: str="atomic_number_direct",
        assertions: list[dict[str,Any]] | None=None,
        memory_operators: list[str] | None=None,
        relations: list[dict[str,Any]] | None=None,
    )->dict[str,Any]:
        address=ElementAddressing.resolve(raw_value,addressing_mode)
        assertion_objects=[]
        for raw in assertions or []:
            assertion_objects.append(ScientificAssertion(
                subject_atomic_number=int(raw.get("subject_atomic_number",address.atomic_number)),
                property_id=str(raw["property_id"]),
                value=raw["value"],
                unit=raw.get("unit"),
                conditions=raw.get("conditions"),
                source=str(raw["source"]),
                observed_at=raw.get("observed_at"),
            ))
        graph=ChemicalSemanticGraph.build(address,assertion_objects,memory_operators,relations)
        controlled=ControlledEnglishCodec.lexicalise(graph)
        parsed=ControlledEnglishCodec.parse(controlled,address,graph["memory_operations"])
        equivalent=(parsed["semantic_root"]==graph["semantic_root"])
        return {
            "schema":"braink.chemical-linguistic-engine.r1/v1",
            "address":asdict(address),
            "element_identity":graph["element_identity"],
            "semantic_graph":graph,
            "controlled_english":controlled,
            "readback_graph":parsed,
            "proof":{
                "equivalence_relation":"canonical semantic graph equality",
                "source_root":graph["semantic_root"],
                "readback_root":parsed["semantic_root"],
                "roundtrip_equivalent":equivalent,
                "controlled_generation":True,
                "provenance_complete":all(bool(p.get("source")) for p in controlled["provenance"]),
            },
        }


def self_test()->dict[str,Any]:
    engine=ChemicalLinguisticEngine()
    direct=engine.execute(
        8,
        "atomic_number_direct",
        assertions=[{
            "property_id":"phase",
            "value":"gas",
            "unit":None,
            "conditions":"specified conditions",
            "source":"test://phase/oxygen",
        }],
        memory_operators=["+1","/1"],
        relations=[{
            "type":"BONDS_WITH",
            "subject_atomic_number":8,
            "object_atomic_number":1,
            "source":"test://relation/oxygen-hydrogen",
        }],
    )
    bucket=engine.execute(7,"bucket_zero_based")
    checks={
        "direct_8_is_oxygen":direct["element_identity"]["symbol"]=="O",
        "bucket_7_is_oxygen":bucket["element_identity"]["symbol"]=="O",
        "addressing_modes_distinct":direct["address"]["addressing_mode"]!=bucket["address"]["addressing_mode"],
        "memory_operator_is_semantic_not_word":direct["semantic_graph"]["memory_operations"][0]["semantic_operation"]=="POSITIVE_REINFORCEMENT",
        "roundtrip_equivalent":direct["proof"]["roundtrip_equivalent"] is True,
        "provenance_complete":direct["proof"]["provenance_complete"] is True,
    }
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks}


if __name__=="__main__":
    print(json.dumps(self_test(),indent=2))

    )
    IDENTITY_RE=re.compile(r"^Element (?P<num>\d+) is (?P<name>[a-z]+) \((?P<symbol>[A-Z][a-z]?)\)\.$")
    PROPERTY_RE=re.compile(
        r"^(?P<name>[A-Z][a-z]+) has (?P<property>[a-z0-9_.:-]+) = "
        r"(?P<value>.*?)(?: \| unit=(?P<unit>.*?))?(?: \| conditions=(?P<conditions>.*?))?"
        r" \| source=(?P<source>.+)\.$"
    )
    RELATION_RE=re.compile(r"^(?P<subject>[A-Z][a-z]+) bonds with (?P<object>[a-z]+) \| source=(?P<source>.+)\.$")

    @staticmethod
    def display(name:str)->str:
        return name[:1].upper()+name[1:]

    @classmethod
    def lexicalise(cls,graph:dict[str,Any])->dict[str,Any]:
        e=graph["element_identity"]
        sentences=[f'Element {e["atomic_number"]} is {e["canonical_name_en"]} ({e["symbol"]}).']
        provenance=[{
            "sentence_index":0,
            "semantic_object":"element_identity",
            "source":f'element/{e["atomic_number"]}/name/iupac/en',
        }]
        for a in graph.get("scientific_assertions",[]):
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} has {a["property_id"]}'
                f' | value={canonical_json(a["value"])}'
                f' | unit={canonical_json(a.get("unit"))}'
                f' | conditions={canonical_json(a.get("conditions"))}'
                f' | source={canonical_json(a["source"])}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"scientific_assertion",
                "property_id":a["property_id"],
                "source":a["source"],
            })
        for rel in graph.get("relations",[]):
            if rel.get("type")!="BONDS_WITH":
                continue
            obj=_BY_NUMBER.get(int(rel["object_atomic_number"]))
            if not obj:
                raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
            source=rel.get("source")
            if not source:
                raise ChemicalLinguisticError("RELATION_SOURCE_REQUIRED")
            sentences.append(
                f'{cls.display(e["canonical_name_en"])} bonds with {obj["canonical_name_en"]} | source={source}.'
            )
            provenance.append({
                "sentence_index":len(sentences)-1,
                "semantic_object":"relation",
                "relation":"BONDS_WITH",
                "source":source,
            })
        return {
            "schema":"braink.controlled-english.r1/v1",
            "sentences":sentences,
            "text":" ".join(sentences),
            "provenance":provenance,
            "source_semantic_root":graph["semantic_root"],
        }

    @classmethod
    def parse(cls,controlled:dict[str,Any],address:NumericAddress,memory_operations:list[dict[str,Any]])->dict[str,Any]:
        sentences=controlled.get("sentences")
        if not isinstance(sentences,list) or not sentences:
            raise ChemicalLinguisticError("CONTROLLED_SENTENCES_REQUIRED")
        m=cls.IDENTITY_RE.fullmatch(sentences[0])
        if not m:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_NOT_PARSEABLE")
        atomic=int(m.group("num"))
        expected=_BY_NUMBER.get(atomic)
        if expected is None:
            raise ChemicalLinguisticError("PARSED_ATOMIC_NUMBER_UNKNOWN")
        if m.group("name")!=expected["canonical_name_en"] or m.group("symbol")!=expected["symbol"]:
            raise ChemicalLinguisticError("IDENTITY_SENTENCE_CONTRADICTS_ELEMENT_TABLE")
        if atomic!=address.atomic_number:
            raise ChemicalLinguisticError("PARSED_IDENTITY_ADDRESS_MISMATCH")

        assertions=[]
        relations=[]
        for sentence in sentences[1:]:
            pm=cls.PROPERTY_RE.fullmatch(sentence)
            if pm:
                if pm.group("name").casefold()!=expected["canonical_name_en"]:
                    raise ChemicalLinguisticError("PROPERTY_SUBJECT_MISMATCH")
                try:
                    value=json.loads(pm.group("value"))
                    unit=json.loads(pm.group("unit"))
                    conditions=json.loads(pm.group("conditions"))
                    source=json.loads(pm.group("source"))
                except json.JSONDecodeError as exc:
                    raise ChemicalLinguisticError("PROPERTY_TYPED_FIELD_DECODE_FAILED") from exc
                assertions.append({
                    "subject_atomic_number":atomic,
                    "property_id":pm.group("property"),
                    "value":value,
                    "unit":unit,
                    "conditions":conditions,
                    "source":source,
                    "observed_at":None,
                })
                continue
            rm=cls.RELATION_RE.fullmatch(sentence)
            if rm:
                obj=_BY_NAME.get(rm.group("object"))
                if obj is None:
                    raise ChemicalLinguisticError("RELATION_OBJECT_UNKNOWN")
                relations.append({
                    "type":"BONDS_WITH",
                    "subject_atomic_number":atomic,
                    "object_atomic_number":obj["atomic_number"],
                    "source":rm.group("source"),
                })
                continue
            raise ChemicalLinguisticError(f"UNSUPPORTED_CONTROLLED_SENTENCE:{sentence}")

        graph={
            "schema":"braink.chemical-semantic-graph.r1/v1",
            "numeric_address":asdict(address),
            "element_identity":dict(expected),
            "scientific_assertions":assertions,
            "memory_operations":memory_operations,
            "relations":relations,
        }
        graph["semantic_root"]=sha256(graph)
        return graph


class ChemicalLinguisticEngine:
    def execute(
        self,
        raw_value: float,
        addressing_mode: str="atomic_number_direct",
        assertions: list[dict[str,Any]] | None=None,
        memory_operators: list[str] | None=None,
        relations: list[dict[str,Any]] | None=None,
    )->dict[str,Any]:
        address=ElementAddressing.resolve(raw_value,addressing_mode)
        assertion_objects=[]
        for raw in assertions or []:
            assertion_objects.append(ScientificAssertion(
                subject_atomic_number=int(raw.get("subject_atomic_number",address.atomic_number)),
                property_id=str(raw["property_id"]),
                value=raw["value"],
                unit=raw.get("unit"),
                conditions=raw.get("conditions"),
                source=str(raw["source"]),
                observed_at=raw.get("observed_at"),
            ))
        graph=ChemicalSemanticGraph.build(address,assertion_objects,memory_operators,relations)
        controlled=ControlledEnglishCodec.lexicalise(graph)
        parsed=ControlledEnglishCodec.parse(controlled,address,graph["memory_operations"])
        equivalent=(parsed["semantic_root"]==graph["semantic_root"])
        return {
            "schema":"braink.chemical-linguistic-engine.r1/v1",
            "address":asdict(address),
            "element_identity":graph["element_identity"],
            "semantic_graph":graph,
            "controlled_english":controlled,
            "readback_graph":parsed,
            "proof":{
                "equivalence_relation":"canonical semantic graph equality",
                "source_root":graph["semantic_root"],
                "readback_root":parsed["semantic_root"],
                "roundtrip_equivalent":equivalent,
                "controlled_generation":True,
                "provenance_complete":all(bool(p.get("source")) for p in controlled["provenance"]),
            },
        }


def self_test()->dict[str,Any]:
    engine=ChemicalLinguisticEngine()
    direct=engine.execute(
        8,
        "atomic_number_direct",
        assertions=[{
            "property_id":"phase",
            "value":"gas",
            "unit":None,
            "conditions":"specified conditions",
            "source":"test://phase/oxygen",
        }],
        memory_operators=["+1","/1"],
        relations=[{
            "type":"BONDS_WITH",
            "subject_atomic_number":8,
            "object_atomic_number":1,
            "source":"test://relation/oxygen-hydrogen",
        }],
    )
    bucket=engine.execute(7,"bucket_zero_based")
    checks={
        "direct_8_is_oxygen":direct["element_identity"]["symbol"]=="O",
        "bucket_7_is_oxygen":bucket["element_identity"]["symbol"]=="O",
        "addressing_modes_distinct":direct["address"]["addressing_mode"]!=bucket["address"]["addressing_mode"],
        "memory_operator_is_semantic_not_word":direct["semantic_graph"]["memory_operations"][0]["semantic_operation"]=="POSITIVE_REINFORCEMENT",
        "roundtrip_equivalent":direct["proof"]["roundtrip_equivalent"] is True,
        "provenance_complete":direct["proof"]["provenance_complete"] is True,
    }
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks}


if __name__=="__main__":
    print(json.dumps(self_test(),indent=2))
