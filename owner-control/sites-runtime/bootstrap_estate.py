#!/usr/bin/env python3
"""Import the recovered historical estate into the executable Sites control plane."""
import json
from pathlib import Path
from app import S
ROOT=Path(__file__).resolve().parent
INDEX=ROOT.parent/"COMPLETE_SITE_ESTATE_INDEX.json"
data=json.loads(INDEX.read_text())
created=[]; existing=[]; domains=[]
native=data.get("recovered_native_site_inventory",{}).get("sites",[])
for item in native:
    slug=item["slug"]
    s=S.site(slug)
    if not s:
        ext=(item.get("project_ids_conflicting_historical") or [None])[0]
        s=S.create_site({"slug":slug,"name":slug.replace("-"," ").title(),"kind":"CHATGPT_SITE","state":"RECOVERED","external_id":ext})
        created.append(slug)
    else: existing.append(slug)
    host=item.get("url","").replace("https://","").rstrip("/")
    if host and not any(d["hostname"]==host for d in S.site(slug)["domains"]):
        S.domain(slug,{"hostname":host,"kind":"NATIVE_CHATGPT_SITE","state":"RECOVERED"}); domains.append(host)
for env in data.get("domain_environment_fabric",{}).get("environments",[]):
    slug=env["slug"]; s=S.site(slug)
    if not s:
        s=S.create_site({"slug":slug,"name":slug.replace("-"," ").title(),"kind":"DOMAIN_ENVIRONMENT","state":"RECOVERED"})
        created.append(slug)
    host=env.get("domain")
    if host and not any(d["hostname"]==host for d in S.site(slug)["domains"]):
        S.domain(slug,{"hostname":host,"kind":"CUSTOM","state":"HISTORICAL_PASS"}); domains.append(host)
out={"created":created,"existing":existing,"domains_bound":domains,"site_count":len(S.sites()),"ledger":S.verify()}
print(json.dumps(out,indent=2))
