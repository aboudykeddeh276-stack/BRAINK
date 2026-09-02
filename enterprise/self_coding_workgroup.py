from __future__ import annotations

import ast
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Iterable, Mapping, Optional


def canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(v: Any) -> str:
    return hashlib.sha256(canonical(v)).hexdigest()


@dataclass(frozen=True)
class WorkModule:
    module_id: str
    instruction: str
    required_capability: str
    input_schema: Mapping[str, str]
    output_schema: Mapping[str, str]
    operation_class: str
    tests: tuple[Mapping[str, Any], ...] = ()
    @property
    def contract_root(self) -> str: return root(asdict(self))


@dataclass(frozen=True)
class AgentMember:
    agent_id: str
    group_id: str
    capabilities: tuple[str, ...]
    roles: tuple[str, ...]


@dataclass(frozen=True)
class SynthesizedFunction:
    function_id: str
    capability: str
    source: str
    source_root: str
    contract_root: str
    status: str


@dataclass(frozen=True)
class ExecutionReceipt:
    module_id: str
    group_id: str
    agent_id: str
    capability: str
    status: str
    output: Mapping[str, Any]
    function_root: Optional[str]
    produced_at_ns: int
    @property
    def receipt_root(self) -> str: return root(asdict(self))


class FunctionRegistry:
    def __init__(self):
        self.functions: Dict[str, Callable[..., Mapping[str, Any]]] = {}
        self.metadata: Dict[str, SynthesizedFunction] = {}
    def register(self, capability, fn, meta):
        self.functions[capability]=fn; self.metadata[capability]=meta
    def resolve(self, capability): return self.functions.get(capability)


class BoundedFunctionSynthesizer:
    SUPPORTED={"PROJECT_FIELDS","FILTER_KEYS","HASH_PAYLOAD","MERGE_DEFAULTS","CLASSIFY_THRESHOLD"}
    def synthesize(self,module:WorkModule):
        if module.operation_class not in self.SUPPORTED: raise ValueError("UNSUPPORTED_SYNTHESIS_CLASS")
        fname="generated_"+hashlib.sha256(module.required_capability.encode()).hexdigest()[:12]
        if module.operation_class=="PROJECT_FIELDS":
            fields=list(module.output_schema.keys()); body=f"return {{k: payload.get(k) for k in {fields!r}}}"
        elif module.operation_class=="FILTER_KEYS":
            allowed=list(module.output_schema.keys()); body=f"return {{k: v for k, v in payload.items() if k in {allowed!r}}}"
        elif module.operation_class=="HASH_PAYLOAD":
            body="return {'sha256': hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}"
        elif module.operation_class=="MERGE_DEFAULTS":
            defaults={k:None for k in module.output_schema.keys()}; body=f"out = {defaults!r}; out.update(payload); return out"
        else:
            body="value=float(payload['value']); threshold=float(payload['threshold']); return {'classification': 'HIGH' if value >= threshold else 'LOW'}"
        source=f"def {fname}(payload):\n    {body}\n"
        ast.parse(source)
        ns={"hashlib":hashlib,"json":json}; exec(compile(source,f"<braink:{fname}>","exec"),ns,ns); fn=ns[fname]
        for case in module.tests:
            if fn(dict(case["input"])) != case["expected"]: raise RuntimeError("SYNTHESIS_TEST_FAILED")
        meta=SynthesizedFunction(f"fn://braink/generated/{fname}",module.required_capability,source,root(source),module.contract_root,"VALIDATED")
        return meta,fn


class WorkGroupRuntime:
    def __init__(self):
        self.agents:Dict[str,AgentMember]={}; self.groups:Dict[str,list[str]]={}; self.registry=FunctionRegistry(); self.synth=BoundedFunctionSynthesizer(); self.receipts=[]; self.evolution_events=[]
    def add_agent(self,member:AgentMember):
        self.agents[member.agent_id]=member; self.groups.setdefault(member.group_id,[]).append(member.agent_id)
    def ensure_capability(self,module:WorkModule):
        existing=self.registry.metadata.get(module.required_capability)
        if existing:return existing
        meta,fn=self.synth.synthesize(module); self.registry.register(module.required_capability,fn,meta)
        self.evolution_events.append({"type":"FUNCTION_SYNTHESIZED_AND_REGISTERED","capability":module.required_capability,"function_id":meta.function_id,"source_root":meta.source_root,"contract_root":meta.contract_root})
        return meta
    def run_group(self,group_id,module,payload):
        ids=list(self.groups.get(group_id,[]))
        if not ids: raise KeyError("UNKNOWN_OR_EMPTY_GROUP")
        meta=self.ensure_capability(module); fn=self.registry.resolve(module.required_capability); out=[]
        for agent_id in ids:
            member=self.agents[agent_id]
            if module.required_capability not in member.capabilities:
                r=ExecutionReceipt(module.module_id,group_id,agent_id,module.required_capability,"DEFERRED_CAPABILITY_HOLE",{"reason":"AGENT_CAPABILITY_NOT_BOUND"},meta.source_root,time.time_ns())
            else:
                r=ExecutionReceipt(module.module_id,group_id,agent_id,module.required_capability,"EXECUTED",dict(fn(dict(payload))),meta.source_root,time.time_ns())
            self.receipts.append(r); out.append(r)
        return out
    def carrier(self):
        return {"schema":"braink.self-coding-workgroup-carrier/v1","agent_root":root({k:asdict(v) for k,v in sorted(self.agents.items())}),"function_root":root({k:asdict(v) for k,v in sorted(self.registry.metadata.items())}),"receipt_root":root([r.receipt_root for r in self.receipts]),"evolution_root":root(self.evolution_events),"groups":{k:list(v) for k,v in sorted(self.groups.items())}}
