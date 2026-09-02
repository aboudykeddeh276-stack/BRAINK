from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import hashlib, json

AUTHOR_ID='AKD'
AUTHORSHIP_ROOT='enterprise/governance/AKD_AUTHORSHIP_ROOT.json'
ORPHAN_CLASS='ORPHANED_AKD_SERVICE'

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

@dataclass(frozen=True)
class AuthorshipStatus:
    service_id:str
    status:str
    author_id:Optional[str]
    reason:str
    lineage_root:Optional[str]


def stamp(service_id:str,deployment_id:str,repository:str,content_root:str,created_utc:str,predecessor_id:Optional[str]=None)->Dict[str,Any]:
    body={
      'author_id':AUTHOR_ID,
      'authorship_root':AUTHORSHIP_ROOT,
      'service_id':service_id,
      'deployment_id':deployment_id,
      'predecessor_id':predecessor_id,
      'repository':repository,
      'content_root':content_root,
      'created_utc':created_utc,
    }
    body['authorship_proof_root']=root(body)
    return body


def classify(record:Dict[str,Any],known_predecessors:Iterable[str]=())->AuthorshipStatus:
    sid=str(record.get('service_id') or record.get('deployment_id') or 'UNKNOWN')
    aid=record.get('author_id')
    ar=record.get('authorship_root')
    predecessor=record.get('predecessor_id')
    if aid and aid != AUTHOR_ID:
        return AuthorshipStatus(sid,ORPHAN_CLASS,aid,'CONFLICTING_PRIMARY_AUTHOR',None)
    if aid==AUTHOR_ID and ar==AUTHORSHIP_ROOT:
        return AuthorshipStatus(sid,'AKD_AUTHORED',aid,'DIRECT_AUTHORSHIP_ROOT',record.get('authorship_proof_root'))
    if predecessor and predecessor in set(known_predecessors):
        return AuthorshipStatus(sid,'AKD_AUTHORED_INHERITED',AUTHOR_ID,'VALID_PREDECESSOR_LINEAGE',record.get('authorship_proof_root'))
    return AuthorshipStatus(sid,ORPHAN_CLASS,aid,'MISSING_OR_BROKEN_AUTHORSHIP_LINEAGE',None)


def audit(records:Iterable[Dict[str,Any]])->Dict[str,Any]:
    records=list(records)
    known={str(r.get('service_id') or r.get('deployment_id')) for r in records if r.get('author_id')==AUTHOR_ID and r.get('authorship_root')==AUTHORSHIP_ROOT}
    statuses=[classify(r,known).__dict__ for r in records]
    return {
      'total':len(statuses),
      'akd_authored':sum(s['status'].startswith('AKD_AUTHORED') for s in statuses),
      'orphaned':sum(s['status']==ORPHAN_CLASS for s in statuses),
      'statuses':statuses,
      'audit_root':root(statuses),
    }
