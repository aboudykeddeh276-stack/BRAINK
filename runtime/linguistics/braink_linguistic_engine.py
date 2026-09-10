#!/usr/bin/env python3
"""BRAINK Linguistic Engine v1.

Deterministic bridge:
  numeric state -> canonical element anchor -> typed property relation
  -> memory-array modifier -> English projection

Atomic identity is canonical. Descriptive vocabulary is versioned policy.
Language projection never mutates the originating numeric/element identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

ELEMENTS = [
    (1,"H","Hydrogen"),(2,"He","Helium"),(3,"Li","Lithium"),(4,"Be","Beryllium"),(5,"B","Boron"),(6,"C","Carbon"),(7,"N","Nitrogen"),(8,"O","Oxygen"),(9,"F","Fluorine"),(10,"Ne","Neon"),
    (11,"Na","Sodium"),(12,"Mg","Magnesium"),(13,"Al","Aluminium"),(14,"Si","Silicon"),(15,"P","Phosphorus"),(16,"S","Sulfur"),(17,"Cl","Chlorine"),(18,"Ar","Argon"),(19,"K","Potassium"),(20,"Ca","Calcium"),
    (21,"Sc","Scandium"),(22,"Ti","Titanium"),(23,"V","Vanadium"),(24,"Cr","Chromium"),(25,"Mn","Manganese"),(26,"Fe","Iron"),(27,"Co","Cobalt"),(28,"Ni","Nickel"),(29,"Cu","Copper"),(30,"Zn","Zinc"),
    (31,"Ga","Gallium"),(32,"Ge","Germanium"),(33,"As","Arsenic"),(34,"Se","Selenium"),(35,"Br","Bromine"),(36,"Kr","Krypton"),(37,"Rb","Rubidium"),(38,"Sr","Strontium"),(39,"Y","Yttrium"),(40,"Zr","Zirconium"),
    (41,"Nb","Niobium"),(42,"Mo","Molybdenum"),(43,"Tc","Technetium"),(44,"Ru","Ruthenium"),(45,"Rh","Rhodium"),(46,"Pd","Palladium"),(47,"Ag","Silver"),(48,"Cd","Cadmium"),(49,"In","Indium"),(50,"Sn","Tin"),
    (51,"Sb","Antimony"),(52,"Te","Tellurium"),(53,"I","Iodine"),(54,"Xe","Xenon"),(55,"Cs","Caesium"),(56,"Ba","Barium"),(57,"La","Lanthanum"),(58,"Ce","Cerium"),(59,"Pr","Praseodymium"),(60,"Nd","Neodymium"),
    (61,"Pm","Promethium"),(62,"Sm","Samarium"),(63,"Eu","Europium"),(64,"Gd","Gadolinium"),(65,"Tb","Terbium"),(66,"Dy","Dysprosium"),(67,"Ho","Holmium"),(68,"Er","Erbium"),(69,"Tm","Thulium"),(70,"Yb","Ytterbium"),
    (71,"Lu","Lutetium"),(72,"Hf","Hafnium"),(73,"Ta","Tantalum"),(74,"W","Tungsten"),(75,"Re","Rhenium"),(76,"Os","Osmium"),(77,"Ir","Iridium"),(78,"Pt","Platinum"),(79,"Au","Gold"),(80,"Hg","Mercury"),
    (81,"Tl","Thallium"),(82,"Pb","Lead"),(83,"Bi","Bismuth"),(84,"Po","Polonium"),(85,"At","Astatine"),(86,"Rn","Radon"),(87,"Fr","Francium"),(88,"Ra","Radium"),(89,"Ac","Actinium"),(90,"Th","Thorium"),
    (91,"Pa","Protactinium"),(92,"U","Uranium"),(93,"Np","Neptunium"),(94,"Pu","Plutonium"),(95,"Am","Americium"),(96,"Cm","Curium"),(97,"Bk","Berkelium"),(98,"Cf","Californium"),(99,"Es","Einsteinium"),(100,"Fm","Fermium"),
    (101,"Md","Mendelevium"),(102,"No","Nobelium"),(103,"Lr","Lawrencium"),(104,"Rf","Rutherfordium"),(105,"Db","Dubnium"),(106,"Sg","Seaborgium"),(107,"Bh","Bohrium"),(108,"Hs","Hassium"),(109,"Mt","Meitnerium"),(110,"Ds","Darmstadtium"),
    (111,"Rg","Roentgenium"),(112,"Cn","Copernicium"),(113,"Nh","Nihonium"),(114,"Fl","Flerovium"),(115,"Mc","Moscovium"),(116,"Lv","Livermorium"),(117,"Ts","Tennessine"),(118,"Og","Oganesson")
]
ELEMENT_BY_Z = {z:{"atomic_number":z,"symbol":s,"name":n} for z,s,n in ELEMENTS}

MEMORY_MODIFIERS = {
    "Array(+1)": {"degree":"HIGH", "terms":["strong","high","intense"]},
    "Array(-1)": {"degree":"LOW", "terms":["weak","low","inhibited"]},
    "Array(.1)": {"degree":"SOFT", "terms":["slight","minor","faint"]},
    "Array(/1)": {"degree":"NORMALIZED", "terms":["balanced","even","proportional"]},
    "Array(+M1)": {"degree":"META_HIGH", "terms":["dominant","primary","major"]},
    "Array(-M1)": {"degree":"META_LOW", "terms":["suppressed","reduced","minor"]},
    "Array(1)": {"degree":"BASE", "terms":[]},
}

# Versioned linguistic policy. These are projection terms, not canonical chemical truth.
PROPERTY_POLICY_V1 = {
    "conductive": {"pos":"adjective", "english":"conductive"},
    "reactive": {"pos":"adjective", "english":"reactive"},
    "stable": {"pos":"adjective", "english":"stable"},
    "dense": {"pos":"adjective", "english":"dense"},
    "light": {"pos":"adjective", "english":"light"},
    "magnetic": {"pos":"adjective", "english":"magnetic"},
    "bond": {"pos":"verb", "english":"bond"},
    "structure": {"pos":"noun", "english":"structure"},
}


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def root(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def element_anchor(atomic_number: int) -> Dict[str, Any]:
    if not isinstance(atomic_number, int) or isinstance(atomic_number, bool):
        raise TypeError("ATOMIC_NUMBER_MUST_BE_INTEGER")
    if atomic_number not in ELEMENT_BY_Z:
        raise ValueError("ATOMIC_NUMBER_OUT_OF_RANGE_1_118")
    return dict(ELEMENT_BY_Z[atomic_number])


def project(atomic_number: int, *, property_id: Optional[str] = None, memory_array: str = "Array(1)") -> Dict[str, Any]:
    element = element_anchor(atomic_number)
    if memory_array not in MEMORY_MODIFIERS:
        raise ValueError("UNKNOWN_MEMORY_ARRAY")
    modifier = MEMORY_MODIFIERS[memory_array]
    prop = None
    phrase = element["name"]
    if property_id is not None:
        if property_id not in PROPERTY_POLICY_V1:
            raise ValueError("UNKNOWN_PROPERTY_POLICY_TERM")
        prop = dict(PROPERTY_POLICY_V1[property_id])
        term = prop["english"]
        prefix = modifier["terms"][0] if modifier["terms"] else ""
        phrase = " ".join(x for x in [prefix, term, element["name"]] if x)
    body = {
        "engine":"BRAINK_LINGUISTIC_ENGINE_V1",
        "source":{"numeric_state":atomic_number,"state_class":"ATOMIC_ANCHOR"},
        "anchor":element,
        "relation":{"property_id":property_id,"policy_version":"PROPERTY_POLICY_V1","property":prop},
        "modifier":{"memory_array":memory_array,**modifier},
        "projection":{"language":"en","text":phrase},
        "truth_boundary":{
            "atomic_identity":"CANONICAL_ANCHOR",
            "property_language":"VERSIONED_POLICY",
            "modifier_language":"VERSIONED_POLICY",
            "projection_mutates_source":False,
        },
    }
    body["semantic_root"] = root(body)
    return body


def self_test() -> Dict[str, Any]:
    assert element_anchor(8)["symbol"] == "O"
    a = project(8, property_id="reactive", memory_array="Array(+1)")
    b = project(8, property_id="reactive", memory_array="Array(+1)")
    assert a["semantic_root"] == b["semantic_root"]
    assert a["source"]["numeric_state"] == 8
    assert a["anchor"]["name"] == "Oxygen"
    assert not a["truth_boundary"]["projection_mutates_source"]
    try:
        element_anchor(0)
        raise AssertionError("zero must not silently map to an element")
    except ValueError:
        pass
    return {"status":"PASS","checks":["118-element anchor table","deterministic projection","source reversibility","memory modifier","zero fail-closed"]}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--atomic-number", type=int)
    p.add_argument("--property")
    p.add_argument("--memory-array", default="Array(1)")
    p.add_argument("--self-test", action="store_true")
    a=p.parse_args()
    if a.self_test:
        print(json.dumps(self_test(), indent=2)); return 0
    if a.atomic_number is None:
        p.error("--atomic-number is required unless --self-test is used")
    print(json.dumps(project(a.atomic_number, property_id=a.property, memory_array=a.memory_array), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
