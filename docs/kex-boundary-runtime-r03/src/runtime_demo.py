#!/usr/bin/env python3
import json
from kex_boundary import *
def main():
 node=NodeDef('kex.demo.hci','il-llm://node/demo-hci',1,'dumb',('label',),('event',),(('surface','html'),('domain','demo')))
 inst=instantiate(node,'html','KEX-DEMO-INSTANCE-001')
 d=CoordinateDirectory();d.register('2,2',node.definition_hash)
 bits=bytes([0,0,1,1,1,1,0,0,0,0,0,0,1,1,1,1])
 enc=boundary_encode(bits);dec=boundary_decode(enc['bytes'])
 print(json.dumps({'seed':'KEX-BND-R03-20260921-7F2A91C4','definition_hash':node.definition_hash,'instance_id':inst.instance_id,'coordinate':d.resolve('2,2'),'binary_sha256':enc['sha256'],'roundtrip':dec['bits']==bits,'html':project_html(node,inst)},sort_keys=True,indent=2))
if __name__=='__main__':main()
