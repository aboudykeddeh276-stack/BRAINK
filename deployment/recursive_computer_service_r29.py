from __future__ import annotations
import argparse
from enterprise.observer2_governed_mutation import Observer2GovernedMutation
from deployment import recursive_computer_service_r26 as base

class GovernedRuntimeHost(base.RuntimeHost):
    def instantiate(self,parent_lineage,child_id):
        parent=self.resolve(parent_lineage); holder={}
        def actuate():
            child=parent.instantiate(child_id); holder['child']=child
            with self._tree_lock: parent.children[child.identity.computer_id]=child
            return {'child_id':child.identity.computer_id}
        governed=Observer2GovernedMutation(parent).execute(
            'SUCCESSOR_CREATED',
            lambda candidate:{**candidate,'children':sorted(set(candidate['children'])|{child_id})},
            actuate,
            lambda post:child_id in post['children'],
        )
        if governed['status']!='EXECUTED': return governed
        out=self.snapshot(holder['child'],'SUCCESSOR_CREATED'); out['observer2_governance']=governed['observer2']; return out
    def write_memory(self,lineage,key,value):
        node=self.resolve(lineage)
        governed=Observer2GovernedMutation(node).execute(
            'MEMORY_WRITE',
            lambda candidate:{**candidate,'memory':{**candidate['memory'],key:value}},
            lambda:node.write_memory(key,value),
            lambda post:post['memory'].get(key)==value,
        )
        if governed['status']!='EXECUTED': return governed
        out=self.snapshot(node); out['observer2_governance']=governed['observer2']; return out
    def write_state(self,lineage,key,value):
        node=self.resolve(lineage)
        governed=Observer2GovernedMutation(node).execute(
            'STATE_WRITE',
            lambda candidate:{**candidate,'state':{**candidate['state'],key:value}},
            lambda:node.write_state(key,value),
            lambda post:post['state'].get(key)==value,
        )
        if governed['status']!='EXECUTED': return governed
        out=self.snapshot(node); out['observer2_governance']=governed['observer2']; return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-root',required=True); parser.add_argument('--computer-id',default='A'); parser.add_argument('--host',default='127.0.0.1'); parser.add_argument('--port',type=int,default=8811); parser.add_argument('--auth-token-file'); parser.add_argument('--allow-unauthenticated-nonloopback',action='store_true')
    args=parser.parse_args(); token=base.load_auth_token(args.auth_token_file); loopback={'127.0.0.1','::1','localhost'}
    if args.host not in loopback and token is None and not args.allow_unauthenticated_nonloopback: raise SystemExit('NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN_OR_EXPLICIT_OVERRIDE')
    base.Handler.host_runtime=GovernedRuntimeHost(args.state_root,args.computer_id); base.Handler.auth_token=token
    server=base.RuntimeServer((args.host,args.port),base.Handler)
    try: server.serve_forever()
    finally: server.server_close()

if __name__=='__main__': main()
