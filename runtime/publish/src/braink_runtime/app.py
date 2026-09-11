from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from .models import ActionExecutionRequest, RegistryObject
from .storage import Store
from .cascade import Cascade

DATA=os.getenv('BRAINK_DATA_DIR','./data'); TOKEN=os.getenv('BRAINK_AUTH_TOKEN','change-me-before-network-exposure')
store=Store(DATA); cascade=Cascade(store)
app=FastAPI(title='BRAINK/KEX Runtime',version='0.1.0')

def auth(x_braink_token:str|None=Header(default=None)):
    if TOKEN and x_braink_token != TOKEN: raise HTTPException(401,'invalid token')

@app.get('/api/health')
def health(): return {'status':'ok','runtime':'braink-kex','version':'0.1.0'}
@app.get('/api/services')
def services(): return {'services':['action-runtime','runtime-registry','proof-ledger','object-registry','cascade']}
@app.get('/cascade')
def stages(): return {'stages':['MOUNT','VERIFY','HYDRATE','RESOLVE','MUTATE','WRITE_BACK','PROOF']}
@app.post('/actions/execute')
def execute(req:ActionExecutionRequest,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    try: return cascade.execute(req)
    except ValueError as e: raise HTTPException(409,str(e))
@app.get('/runtime/{target:path}')
def runtime(target:str):
    v,version=store.get_state(target); return {'target':target,'version':version,'state':v}
@app.get('/api/proof-ledger')
def ledger(): return {'entries':store.read_ledger()}
@app.put('/registry/objects/{object_id}')
def put_object(object_id:str,obj:RegistryObject,x_braink_token:str|None=Header(default=None)):
    auth(x_braink_token)
    if obj.object_id != object_id: raise HTTPException(400,'object_id mismatch')
    store.put_object(object_id,obj.model_dump(mode='json')); return obj
@app.get('/registry/objects/{object_id}')
def get_object(object_id:str):
    obj=store.get_object(object_id)
    if not obj: raise HTTPException(404,'not found')
    return obj
@app.get('/registry/objects')
def list_objects(): return {'objects':store.list_objects()}
