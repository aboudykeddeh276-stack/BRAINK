from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"mcp"))

from runtime.linguistics.chemical_linguistic_engine_r1 import (
    ChemicalLinguisticEngine,
    ControlledEnglishCodec,
    ChemicalLinguisticError,
)
from braink_process_adapter.backend import BrainkProcessBackend


def require(value,message):
    if not value:
        raise AssertionError(message)


def main():
    engine=ChemicalLinguisticEngine()

    direct=engine.execute(
        8,
        "atomic_number_direct",
        assertions=[{
            "property_id":"electronegativity",
            "value":3.44,
            "unit":"Pauling",
            "conditions":"reference scale",
            "source":"test://nist-like/electronegativity",
            "observed_at":"2026-09-30T00:00:00Z",
        }],
        memory_operators=["+1","/1"],
        relations=[{
            "type":"BONDS_WITH",
            "subject_atomic_number":8,
            "object_atomic_number":1,
            "source":"test://relation/oxygen-hydrogen",
        }],
    )
    require(direct["element_identity"]["symbol"]=="O","8 did not resolve to oxygen")
    require(direct["proof"]["roundtrip_equivalent"] is True,"direct roundtrip failed")
    require(direct["readback_graph"]["scientific_assertions"][0]["value"]==3.44,"numeric property type lost")
    require(direct["readback_graph"]["scientific_assertions"][0]["observed_at"]=="2026-09-30T00:00:00Z","observation provenance lost")
    require(direct["readback_graph"]["memory_operations"][0]["semantic_operation"]=="POSITIVE_REINFORCEMENT","memory semantic operation lost")

    bucket=engine.execute(7,"bucket_zero_based")
    require(bucket["element_identity"]["symbol"]=="O","bucket 7 did not resolve to oxygen")
    require(bucket["address"]["addressing_mode"]=="bucket_zero_based","bucket addressing mode lost")
    require(bucket["address"]["raw_value"]==7.0,"raw bucket address lost")

    closed=dict(direct["controlled_english"])
    closed["sentences"]=list(closed["sentences"])+["Oxygen is magnetic."]
    rejected=False
    try:
        ControlledEnglishCodec.parse(closed)
    except ChemicalLinguisticError:
        rejected=True
    require(rejected,"unsupported controlled-language assertion was accepted")

    missing_source=False
    try:
        engine.execute(8,assertions=[{
            "property_id":"phase",
            "value":"gas",
            "unit":None,
            "conditions":"specified conditions",
            "source":"",
        }])
    except ChemicalLinguisticError:
        missing_source=True
    require(missing_source,"property without provenance source was accepted")

    tampered=dict(bucket["controlled_english"])
    tampered["sentences"]=list(tampered["sentences"])
    tampered["sentences"][1]="Element 8 is nitrogen (N)."
    tamper_rejected=False
    try:
        ControlledEnglishCodec.parse(tampered)
    except ChemicalLinguisticError:
        tamper_rejected=True
    require(tamper_rejected,"tampered element identity was accepted")

    os.environ["BRAINK_MCP_HMAC_KEY_HEX"]="4b"*32
    with tempfile.TemporaryDirectory(prefix="braink-chemical-linguistics-") as tmp:
        backend=BrainkProcessBackend(state_dir=Path(tmp))
        work_id="WORK-CHEM-LING-R1"
        actor="agent://chemical-linguistics-test"
        lease=backend.acquire_lease(work_id,actor)
        context={
            "work_id":work_id,
            "actor_id":actor,
            "lease_epoch":lease["epoch"],
            "scopes":["linguistics:read"],
        }
        result=backend.invoke_capability(
            "linguistics.chemical_codec",
            context,
            {
                "raw_value":26,
                "addressing_mode":"atomic_number_direct",
                "assertions":[{
                    "property_id":"sample_property",
                    "value":{"magnitude":1,"state":"test"},
                    "unit":None,
                    "conditions":"test-only",
                    "source":"test://property/iron",
                }],
                "memory_operators":["-1"],
                "relations":[],
            },
            "chemical-linguistic-test",
        )
        require(result["status"]=="SUCCEEDED","MCP governed capability invocation failed")
        payload=result["result"]
        require(payload["element_identity"]["symbol"]=="Fe","MCP capability did not resolve iron")
        require(payload["proof"]["roundtrip_equivalent"] is True,"MCP capability roundtrip failed")

    report={
        "schema":"braink.chemical-linguistic-engine.r1.test/v1",
        "status":"PASS",
        "checks":{
            "direct_atomic_addressing":True,
            "bucket_addressing_distinct":True,
            "typed_property_roundtrip":True,
            "observation_provenance_roundtrip":True,
            "memory_operator_semantic_roundtrip":True,
            "closed_generation_rejects_unsupported_assertion":True,
            "missing_provenance_rejected":True,
            "tampered_identity_rejected":True,
            "governed_mcp_capability":True,
        },
    }
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
