#!/usr/bin/env python3
"""@Sites MCP server: ChatGPT/Codex tool surface for BRAINK × KEX Sites."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUNTIME=HERE.parent.parent/"owner-control"/"sites-runtime"
sys.path.insert(0,str(RUNTIME))
from app import S\nNATIVE=HERE.parent/"native"\nCAPS=HERE.parent/"CAPABILITY_REGISTRY.json"
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise SystemExit("Install dependency: pip install 'mcp>=1.0'") from e

mcp=FastMCP(
    "@Sites",
    instructions=("Owner-controlled Sites operator. Resolve an existing site before mutation. "
                  "Never equate a domain, repository, version, deployment, or public readback. "
                  "For publishing: inspect site -> create immutable version -> deploy -> public readback -> verify ledger. "
                  "Never report provider success without adapter/readback evidence.")
)

@mcp.tool()
def sites_list() -> dict:
    """List persistent Site identities and states."""
    return {"sites":S.sites(),"ledger":S.verify()}

@mcp.tool()
def site_get(site_id_or_slug:str) -> dict:
    """Read one Site with domains, immutable versions and deployment receipts."""
    s=S.site(site_id_or_slug)
    return s or {"error":"SITE_NOT_FOUND","site":site_id_or_slug}

@mcp.tool()
def site_create(slug:str,name:str,kind:str="SITE",external_id:str|None=None) -> dict:
    """Create a persistent owner-controlled Site identity."""
    return S.create_site({"slug":slug,"name":name,"kind":kind,"external_id":external_id})

@mcp.tool()
def domain_bind(site_id_or_slug:str,hostname:str,kind:str="CUSTOM",state:str="RECORDED") -> dict:
    """Bind a domain identity to a Site. This does not claim DNS, TLS or public deployment success."""
    return S.domain(site_id_or_slug,{"hostname":hostname,"kind":kind,"state":state})

@mcp.tool()
def version_create(site_id_or_slug:str,files:dict[str,str],message:str="") -> dict:
    """Create an immutable multi-file Site version with SHA-256 evidence."""
    return S.version(site_id_or_slug,{"files":files,"message":message})

@mcp.tool()
def deploy(site_id_or_slug:str,version_id:str|None=None,adapter:str="local",target:str|None=None) -> dict:
    """Deploy an immutable version through a configured adapter and persist the receipt."""
    p={"adapter":adapter}
    if version_id:p["version_id"]=version_id
    if target:p["target"]=target
    return S.deploy(site_id_or_slug,p)

@mcp.tool()
def public_readback(site_id_or_slug:str,url:str,timeout:float=10) -> dict:
    """Perform outside-in HTTP readback and ledger the observed response."""
    return S.readback(site_id_or_slug,{"url":url,"timeout":timeout})

@mcp.tool()
def ledger_verify() -> dict:
    """Verify the hash-chained @Sites event ledger."""
    return S.verify()

@mcp.tool()
def estate_import() -> dict:
    """Import recovered historical Site/domain identities into the executable registry without inventing current-live state."""
    index=json.loads((RUNTIME.parent/"COMPLETE_SITE_ESTATE_INDEX.json").read_text())
    created=[]; bound=[]
    native=index.get("recovered_native_site_inventory",{}).get("sites",[])
    envs=index.get("domain_environment_fabric",{}).get("environments",[])
    for item in native:
        slug=item["slug"]
        if not S.site(slug):
            ids=item.get("project_ids_conflicting_historical") or []
            S.create_site({"slug":slug,"name":slug.replace("-"," ").title(),"kind":"CHATGPT_SITE","state":"RECOVERED","external_id":ids[0] if len(ids)==1 else None}); created.append(slug)
        host=item.get("url","").replace("https://","").rstrip("/")
        if host and not any(x["hostname"]==host for x in S.site(slug)["domains"]):
            S.domain(slug,{"hostname":host,"kind":"NATIVE_CHATGPT_SITE","state":"RECOVERED"}); bound.append(host)
    for e in envs:
        slug=e["slug"]
        if not S.site(slug):
            S.create_site({"slug":slug,"name":slug.replace("-"," ").title(),"kind":"DOMAIN_ENVIRONMENT","state":"RECOVERED"}); created.append(slug)
        host=e.get("domain")
        if host and not any(x["hostname"]==host for x in S.site(slug)["domains"]):
            S.domain(slug,{"hostname":host,"kind":"CUSTOM","state":"HISTORICAL_PASS"}); bound.append(host)
    return {"created":created,"domains_bound":bound,"site_count":len(S.sites()),"ledger":S.verify()}

if __name__=="__main__":
    mcp.run(transport=os.environ.get("SITES_MCP_TRANSPORT","streamable-http"))
