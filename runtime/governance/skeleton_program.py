#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse, hashlib, json, re, datetime
SCHEMA_VERSION="braink.governance.r16"
VALID_KINDS={"SECTOR","MODULE","FUNCTION","SERVICE","AGENT","DOMAIN","RUNTIME","WORKFLOW","CONTROL"}
def slug(v): return re.sub(r"[^A-Za-z0-9._-]+","-",v.strip()).strip("-").lower()
def sha256_bytes(data): return hashlib.sha256(data).hexdigest()
@dataclass
class GovernedUnit:
    unit_id:str; kind:str; name:str; sector:str; owner:str; author:str; authority:str; purpose:str; runtime_boundary:str; proof_condition:str; platform_contract:list[str]; parent_unit_id:str|None=None
    def validate(self):
        if self.kind not in VALID_KINDS: raise ValueError(f"unsupported kind: {self.kind}")
        for f in ("unit_id","name","sector","owner","author","authority","purpose","runtime_boundary","proof_condition"):
            if not getattr(self,f): raise ValueError(f"missing required field: {f}")
        if not self.platform_contract: raise ValueError("platform_contract must contain at least one target")
def build_pack(unit):
    unit.validate(); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {"schema":SCHEMA_VERSION,"unit":asdict(unit),"governance":{"status":"DRAFT","promotion_rule":"IMPLEMENTED_AND_VERIFIED_ONLY","change_authority":unit.authority,"accountable_owner":unit.owner,"authorship":unit.author,"required_readback":True,"unknown_remains_unknown":True,"evidence_over_claim":True},"controls":{"process":{"lifecycle":["DISCOVER","DESIGN","IMPLEMENT","TEST","VERIFY","DOCUMENT","DEPLOY","READBACK","OPERATE","REVIEW","RETIRE"],"mandatory_gates":["REQUIREMENT","AUTHORITY","IMPLEMENTATION","VERIFICATION","READBACK","ROLLBACK"]},"workflow":{"entry_condition":"REQUEST_OR_AUTHORISED_TRIGGER","exit_condition":unit.proof_condition,"failure_state":"BLOCKED_OR_FAILED_WITH_EVIDENCE","rollback_required":True},"filing":{"root":f"KEX://GOVERNANCE/{slug(unit.sector)}/{slug(unit.kind)}/{slug(unit.name)}/","canonical_file_prefix":f"{slug(unit.sector)}__{slug(unit.kind)}__{slug(unit.name)}","revision_policy":"IMMUTABLE_RECEIPTS_VERSIONED_CONTROLS","hash_required":True},"help":{"operator_runbook_required":True,"admin_runbook_required":True,"failure_guide_required":True,"recovery_guide_required":True},"cross_platform":{"targets":unit.platform_contract,"semantic_contract_must_remain_stable":True,"adapter_boundary_required":True,"platform_specific_overrides_must_be_declared":True}},"artifacts":{"CONTROL.md":"governance and authority contract","PROCESS.md":"process definition and lifecycle","WORKFLOW.md":"workflow states, gates and transitions","RUNBOOK.md":"operator instructions","ADMIN.md":"administration and authority controls","HELP.md":"user/operator help and failure handling","ACCOUNTABILITY.md":"authorship, ownership, approvals and receipts","ADAPTATION.md":"cross-platform and cross-sector adapter contract","unit.control.json":"machine-readable canonical control state"},"created_at":now}
def write_pack(unit,destination):
    pack=build_pack(unit); target=destination/slug(unit.sector)/slug(unit.kind)/slug(unit.name); target.mkdir(parents=True,exist_ok=True)
    (target/'unit.control.json').write_text(json.dumps(pack,indent=2))
    templates={'CONTROL.md':f'# {unit.name} — Control\n\nUnit ID: `{unit.unit_id}`\n\nAuthority: `{unit.authority}`\n\nOwner: `{unit.owner}`\n\nAuthor: `{unit.author}`\n\nPurpose: {unit.purpose}\n\nPromotion requires implementation, verification and readback against: `{unit.proof_condition}`.\n','PROCESS.md':'# Process\n\nDISCOVER → DESIGN → IMPLEMENT → TEST → VERIFY → DOCUMENT → DEPLOY → READBACK → OPERATE → REVIEW → RETIRE\n','WORKFLOW.md':'# Workflow\n\nEvery transition requires actor, authority, input state, mutation, evidence, result state and rollback path.\n','RUNBOOK.md':f'# Operator Runbook\n\nRuntime boundary: {unit.runtime_boundary}\n\nDo not promote unverified state. Record each execution receipt under the unit filing root.\n','ADMIN.md':'# Administration\n\nAdministrative actions require named authority, actor identity, mutation scope, approval rule, proof target, readback and rollback.\n','HELP.md':'# Help\n\nDocument normal operation, required inputs, expected outputs, known failure states, recovery procedure and escalation owner.\n','ACCOUNTABILITY.md':f'# Accountability\n\nAuthor: {unit.author}\n\nAccountable owner: {unit.owner}\n\nAuthority: {unit.authority}\n\nEvery material change carries actor, timestamp, revision, digest, reason, verification and approval state.\n','ADAPTATION.md':'# Adaptation\n\nPreserve semantic contracts across platforms. Platform-specific behavior belongs behind declared adapters and must not silently change unit identity, lineage, proof conditions or authority.\n'}
    for n,b in templates.items(): (target/n).write_text(b)
    manifest={p.name:sha256_bytes(p.read_bytes()) for p in sorted(target.iterdir()) if p.is_file()}
    (target/'MANIFEST.sha256.json').write_text(json.dumps(manifest,indent=2)); return target
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--kind',required=True,choices=sorted(VALID_KINDS)); ap.add_argument('--name',required=True); ap.add_argument('--sector',required=True); ap.add_argument('--unit-id',required=True); ap.add_argument('--owner',required=True); ap.add_argument('--author',required=True); ap.add_argument('--authority',required=True); ap.add_argument('--purpose',required=True); ap.add_argument('--runtime-boundary',required=True); ap.add_argument('--proof-condition',required=True); ap.add_argument('--platform',action='append',required=True); ap.add_argument('--parent-unit-id'); ap.add_argument('--out',default='./governed'); a=ap.parse_args()
    unit=GovernedUnit(a.unit_id,a.kind,a.name,a.sector,a.owner,a.author,a.authority,a.purpose,a.runtime_boundary,a.proof_condition,a.platform,a.parent_unit_id); t=write_pack(unit,Path(a.out)); print(json.dumps({"status":"PASS","path":str(t),"schema":SCHEMA_VERSION},indent=2))
if __name__=='__main__': main()
