from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .models import ActionExecutionRequest, RegistryObject
from .storage import Store
from .cascade import Cascade
from .workbook import WorkbookService
from .saas import SaaSNode, ProvisioningIntent
from .estate_bindings import EstateBindings

DATA=os.getenv('BRAINK_DATA_DIR','./data')
TOKEN=os.getenv('BRAINK_AUTH_TOKEN','change-me-before-network-exposure')
store=Store(DATA)
cascade=Cascade(store)
workbooks=WorkbookService()
saas=SaaSNode(DATA)
estate=EstateBindings()
app=FastAPI(title='BRAINK/KEX Runtime',version='0.2.1')

def auth(x_braink_token:str|None=Header(default=None)):
    if TOKEN and x_braink_token != TOKEN:
        raise HTTPException(401,'invalid token')

class WorkbookReadRequest(BaseModel):
    path: str
    sheet: str
    min_row: int = 1
    max_row: int | None = None

class WorkbookAppendRequest(BaseModel):
    path: str
    sheet: str
    values: list = Field(default_factory=list)

class SaaSSystemRequest(BaseModel):
    system_id: str
    name: str
    adapter_uri: str
    runtime_uri: str | None = None
    metadata: dict = Field(default_factory=dict)

class SaaSTenantRequest(BaseModel):
    tenant_id: str
    display_name: str
    metadata: dict = Field(default_factory=dict)

class SaaSEntitlementRequest(BaseModel):
    tenant_id: str
    system_id: str
    service_id: str
    plan: str = 'standard'
    limits: dict = Field(default_factory=dict)

class SaaSProvisionRequest(BaseModel):
    tenant_id: str
    system_id: str
    service_id: str
    plan: str = 'standard'
    requested_by: str

@app.get('/api/health')
def health():
    return {'status':'ok','runtime':'braink-kex','version':'0.2.1'}

@app.get('/api/services')
def services():
    return {'services':['action-runtime','workbook-data','connector','runtime-registry','proof-ledger','object-registry','cascade','mesh-status','route-registry','uri-resolver','saas-node','saas-estate-bindings']}

@app.get('/api/routes')
def routes():
    return {'routes':[r.path for r in app.routes if hasattr(r,'path')]}

@app.get('/api/resolve')
def resolve(uri:str):
    obj=store.get_object(uri)
    if obj:
        return {'uri':uri,'resolved':True,'object':obj}
    state,version=store.get_state(uri)
    return {'uri':uri,'resolved':bool(version),'version':version,'state':state}

@app.get('/mesh')
def mesh():
    return {'status':'local-single-node','nodes':[{'id':'local','state':'active'}]}

@app.get('/cascade')
def stages():
    return {'stages':['MOUNT','VERIFY','HYDRATE','RESOLVE','MUTATE','WRITE_BACK','PROOF']}

@app.post('/actions/execute')
def execute(req:ActionExecutionRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        return cascade.execute(req)
    except ValueError as e:
        raise HTTPException(409,str(e))

@app.get('/runtime/{target:path}')
def runtime(target:str):
    v,version=store.get_state(target)
    return {'target':target,'version':version,'state':v}

@app.get('/api/proof-ledger')
def ledger():
    return {'entries':store.read_ledger()}

@app.put('/registry/objects/{object_id}')
def put_object(object_id:str,obj:RegistryObject,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    if obj.object_id != object_id:
        raise HTTPException(400,'object_id mismatch')
    store.put_object(object_id,obj.model_dump(mode='json'))
    return obj

@app.get('/registry/objects/{object_id}')
def get_object(object_id:str):
    obj=store.get_object(object_id)
    if not obj:
        raise HTTPException(404,'not found')
    return obj

@app.get('/registry/objects')
def list_objects():
    return {'objects':store.list_objects()}

@app.post('/workbooks/read')
def workbook_read(req:WorkbookReadRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        rows=workbooks.read_rows(req.path,req.sheet,req.min_row,req.max_row)
        return {'rows':rows}
    except Exception as e:
        raise HTTPException(400,f'workbook_read_failed: {e}')

@app.post('/workbooks/append')
def workbook_append(req:WorkbookAppendRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        return workbooks.append_row(req.path,req.sheet,req.values)
    except Exception as e:
        raise HTTPException(400,f'workbook_append_failed: {e}')

@app.post('/connector/execute-action')
def connector_execute(req:ActionExecutionRequest,x_braink_token:str|None=Header(default=None)):
    return execute(req,x_braink_token)

@app.get('/connector/system-health')
def connector_health():
    return health()

@app.get('/connector/mesh-status')
def connector_mesh():
    return mesh()

@app.get('/saas/health')
def saas_health():
    return {'status':'ok','node':'saas','version':'0.2.1','systems':len(saas.list_systems())}

@app.put('/saas/systems/{system_id}')
def saas_register_system(system_id:str,req:SaaSSystemRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    if system_id != req.system_id:
        raise HTTPException(400,'system_id mismatch')
    return saas.register_system(req.system_id,req.name,req.adapter_uri,req.runtime_uri,req.metadata)

@app.get('/saas/systems')
def saas_systems():
    return {'systems':saas.list_systems()}

@app.put('/saas/tenants/{tenant_id}')
def saas_upsert_tenant(tenant_id:str,req:SaaSTenantRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    if tenant_id != req.tenant_id:
        raise HTTPException(400,'tenant_id mismatch')
    return saas.upsert_tenant(req.tenant_id,req.display_name,req.metadata)

@app.put('/saas/entitlements')
def saas_entitle(req:SaaSEntitlementRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        return saas.grant_entitlement(req.tenant_id,req.system_id,req.service_id,req.plan,req.limits)
    except ValueError as e:
        raise HTTPException(404,str(e))

@app.get('/saas/resolve')
def saas_resolve(tenant_id:str,system_id:str,service_id:str):
    try:
        return saas.resolve(tenant_id,system_id,service_id)
    except PermissionError as e:
        raise HTTPException(403,str(e))
    except ValueError as e:
        raise HTTPException(404,str(e))

@app.post('/saas/provision')
def saas_provision(req:SaaSProvisionRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        return saas.request_provisioning(ProvisioningIntent(**req.model_dump()))
    except PermissionError as e:
        raise HTTPException(403,str(e))
    except ValueError as e:
        raise HTTPException(404,str(e))

@app.get('/saas/audit')
def saas_audit(limit:int=100,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    return {'events':saas.audit_events(limit)}

@app.get('/saas/bindings')
def saas_bindings(x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    return estate.status()

@app.post('/saas/provision-plan')
def saas_provision_plan(req:SaaSProvisionRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try:
        saas.resolve(req.tenant_id,req.system_id,req.service_id)
    except PermissionError as e:
        raise HTTPException(403,str(e))
    except ValueError as e:
        raise HTTPException(404,str(e))
    return estate.provisioning_plan(tenant_id=req.tenant_id,system_id=req.system_id,service_id=req.service_id,plan=req.plan)

@app.post('/saas/actuate-fabric')
def saas_actuate_fabric(x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    result=estate.actuate_fabric()
    if result.get('status') != 'PASS':
        raise HTTPException(409,result)
    return result
