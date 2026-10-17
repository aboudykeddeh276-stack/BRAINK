from __future__ import annotations
import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    'substrate','state','interfaces','producer','consumer','address_space',
    'communication_mechanism','virtualisation_type','persistence','authority','proof'
)
DISTINCT_CLASSES = {
    'COMPUTATION','STORAGE','ADDRESSING','COMMUNICATION','TRANSPORT','VIRTUALISATION','AUTHORITY'
}

class SystemContractRegistry:
    def __init__(self, graph_path: str | Path):
        self.graph_path = Path(graph_path)
        self.graph = json.loads(self.graph_path.read_text(encoding='utf-8'))

    def verify(self) -> dict[str, Any]:
        errors=[]
        classes=set(self.graph.get('classification_law',[]))
        if classes != DISTINCT_CLASSES:
            errors.append('CLASSIFICATION_LAW_MISMATCH')
        components=self.graph.get('components',{})
        if not components:
            errors.append('NO_COMPONENTS')
        authorities=set()
        for cid, spec in components.items():
            missing=[f for f in REQUIRED_FIELDS if f not in spec]
            if missing: errors.append(f'{cid}:MISSING:{",".join(missing)}')
            unknown=set(spec.get('class',[]))-DISTINCT_CLASSES
            if unknown: errors.append(f'{cid}:UNKNOWN_CLASS:{sorted(unknown)}')
            authority=spec.get('authority')
            if authority: authorities.add(authority)
            interfaces=spec.get('interfaces')
            if not interfaces: errors.append(f'{cid}:NO_INTERFACE')
        return {
            'status':'VERIFIED' if not errors else 'INVALID',
            'component_count':len(components),
            'authorities':sorted(authorities),
            'errors':errors,
        }

    def snapshot(self) -> dict[str, Any]:
        result=self.verify()
        return {**result,'schema':self.graph.get('schema'),'components':self.graph.get('components',{}),'required_edges':self.graph.get('required_edges',[])}
