import argparse,json,os
from braink_runtime.report03_mesh import DurablePaxosToT,Server
p=argparse.ArgumentParser();p.add_argument("--node",required=True);p.add_argument("--members",required=True);p.add_argument("--wal",required=True);p.add_argument("--secret",required=True);p.add_argument("--endpoint-file",required=True);a=p.parse_args()
st=DurablePaxosToT(a.node,tuple(a.members.split(",")),a.wal,a.secret);srv=Server(("127.0.0.1",0),st)
with open(a.endpoint_file,"w") as f:json.dump({"node":a.node,"endpoint":f"127.0.0.1:{srv.server_address[1]}","pid":os.getpid()},f);f.flush();os.fsync(f.fileno())
try:srv.serve_forever()
finally:srv.server_close()