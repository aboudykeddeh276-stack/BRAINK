from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .models import ActionExecutionRequest, RegistryObject
from .storage import Store
from .cascade import Cascade
from .workbook import WorkbookService

DATA=os.getenv('BRAINK_DATA_DIR','./data')
TOKEN=os.getenv('BRAINK_AUTH_TOKEN','change-me-before-network-exposure')
store=Store(DATA)
cascade=Cascade(store)
workbooks=WorkbookService()
app=FastAPI(title='BRAINK/KEX Runtime',version='0.1.1')

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

@app.get('/api/health')
def health():
    return {'status':'ok','runtime':'braink-kex','version':'0.1.1'}

@app.get('/api/services')
def services():
    return {'services':['action-runtime','workbook-data','connector','runtime-registry','proof-ledger','object-registry','cascade','mesh-status','route-registry','uri-resolver']}

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
