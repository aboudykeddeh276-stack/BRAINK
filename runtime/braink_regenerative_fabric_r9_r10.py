from pathlib import Path
import json, hashlib, os

BLOCK = 4096
DISK_BYTES = 64 * 1024 * 1024
SUPER_OFF = 0
BRAINK_OFF = 256 * BLOCK
OBJECT_OFF = 512 * BLOCK
ZEROLESS = [-3,-2,1,2,3]

def sha(b): return hashlib.sha256(b).hexdigest()

def write_block(fd, off, obj):
    raw = json.dumps(obj, sort_keys=True, separators=(",",":")).encode()
    if len(raw) > BLOCK - 8: raise RuntimeError("E_BLOCK_TOO_LARGE")
    buf = bytearray(BLOCK); buf[0:4] = len(raw).to_bytes(4, "big"); buf[8:8+len(raw)] = raw
    os.pwrite(fd, bytes(buf), off); return sha(raw)

def read_block(fd, off):
    head = os.pread(fd, 8, off)
    if len(head) < 8: return None
    n = int.from_bytes(head[:4], "big")
    if n <= 0 or n > BLOCK - 8: return None
    raw = os.pread(fd, n, off+8)
    return {"obj": json.loads(raw.decode()), "raw": raw, "sha256": sha(raw)}

def init_machine(path, machine_id, braink_id, lineage_root, parent_machine=None, parent_braink=None):
    fd = os.open(path, os.O_CREAT|os.O_RDWR|os.O_TRUNC, 0o644); os.ftruncate(fd, DISK_BYTES)
    root = {"schema":"braink.root.r9","braink_id":braink_id,"machine_id":machine_id,"lineage_root":lineage_root,"parent_machine":parent_machine,"parent_braink":parent_braink,"medium_root":f"DEVICE://{machine_id}/STORAGE/BLOCK0","controller_root":f"KEX_STORAGE_CONTROLLER://{machine_id}","storage_root":f"KEX://MACHINE/{machine_id}/STORAGE/","vfs_root":f"KEX://VFS/{machine_id}/","vfs_role":"RESOLVER_ONLY","network_root":f"LEX://BRAINK/{machine_id}","vector_root":f"VEC://MACHINE/{machine_id}/LOCAL","observer_root":f"OBS://BRAINK/{machine_id}/R9","proof_root":f"PROOF://BRAINK/{machine_id}/R9","zero_less_geometry":ZEROLESS,"state":"RESIDENT"}
    rh = write_block(fd, BRAINK_OFF, root)
    superblock = {"schema":"kex.braink.machine.r9","machine_id":machine_id,"braink_id":braink_id,"controller":"KEX_STORAGE_CONTROLLER","disk_bytes":DISK_BYTES,"block_bytes":BLOCK,"zero_less_geometry":ZEROLESS,"braink_root_lba":256,"braink_root_sha256":rh,"state":"BRAINK_RESIDENT"}
    sh = write_block(fd, SUPER_OFF, superblock); os.fsync(fd); os.close(fd)
    return {"root":root,"root_sha256":rh,"super_sha256":sh}

def inspect_machine(path):
    fd = os.open(path, os.O_RDONLY); s = read_block(fd, SUPER_OFF); r = read_block(fd, s["obj"]["braink_root_lba"] * BLOCK) if s else None; o = read_block(fd, OBJECT_OFF); os.close(fd)
    return {"super":s,"root":r,"object":o}

def derive_descendant(parent_path, child_path):
    pr = inspect_machine(parent_path)["root"]["obj"]
    suffix = hashlib.sha256(f'{pr["machine_id"]}|{pr["braink_id"]}|child:1'.encode()).hexdigest()[:12].upper()
    child_machine = f"KEX-MACHINE-002-{suffix}"; child_braink = f"BRAINK::{child_machine}::R9"; lineage = f'{pr["lineage_root"]}::DESCENDANT::{suffix}'
    created = init_machine(child_path, child_machine, child_braink, lineage, pr["machine_id"], pr["braink_id"])
    return {"action":"R9_DESCENDANT_GENERATION","parent_machine":pr["machine_id"],"parent_braink":pr["braink_id"],"child_machine":child_machine,"child_braink":child_braink,"child_lineage":lineage,"identity_distinct":child_machine != pr["machine_id"] and child_braink != pr["braink_id"],"ancestry_preserved":created["root"]["parent_machine"] == pr["machine_id"] and created["root"]["parent_braink"] == pr["braink_id"],"child_root_sha256":created["root_sha256"]}

def boot_verify(path):
    m=inspect_machine(path); s,r=m["super"],m["root"]
    checks={"super_present":bool(s),"root_present":bool(r),"hash_match":bool(s and r and s["obj"]["braink_root_sha256"]==r["sha256"]),"machine_match":bool(s and r and s["obj"]["machine_id"]==r["obj"]["machine_id"]),"braink_match":bool(s and r and s["obj"]["braink_id"]==r["obj"]["braink_id"]),"vfs_resolver_only":bool(r and r["obj"].get("vfs_role")=="RESOLVER_ONLY"),"controller_present":bool(r and r["obj"].get("controller_root")),"medium_present":bool(r and r["obj"].get("medium_root")),"network_present":bool(r and r["obj"].get("network_root")),"observer_present":bool(r and r["obj"].get("observer_root"))}
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"machine":r["obj"] if r else None}

def write_object(path, object_id, payload, lineage):
    fd=os.open(path,os.O_RDWR); obj={"schema":"braink.object.r10","object_id":object_id,"lexical_id":f"LEX://OBJECT/{object_id}","payload":payload,"payload_sha256":sha(payload.encode()),"lineage":lineage,"revision":"R10-1","state":"COMMITTED"}; oh=write_block(fd,OBJECT_OFF,obj); os.fsync(fd); os.close(fd); return {"object":obj,"object_sha256":oh}

def replicate_object(src,dst):
    sm=inspect_machine(src); src_obj=sm["object"]["obj"]; dm=inspect_machine(dst); replica=dict(src_obj); replica["replica_of_lineage"]=src_obj["lineage"]; replica["lineage"]=dm["root"]["obj"]["lineage_root"]; replica["state"]="REPLICA_COMMITTED"; fd=os.open(dst,os.O_RDWR); rh=write_block(fd,OBJECT_OFF,replica); os.fsync(fd); os.close(fd); return {"source_object_sha256":sm["object"]["sha256"],"replica_object_sha256":rh,"payload_sha256_equal":replica["payload_sha256"]==src_obj["payload_sha256"],"lineage_distinct":replica["lineage"]!=src_obj["lineage"],"canonical_object_equal":replica["object_id"]==src_obj["object_id"]}

def main():
    m1=Path("/mnt/data/BRAINK_MACHINE_001_R9.vdisk"); m2=Path("/mnt/data/BRAINK_MACHINE_002_R9.vdisk")
    init_machine(m1,"KEX-MACHINE-001","BRAINK::KEX-MACHINE-001::R9","BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS")
    r9=derive_descendant(m1,m2); r9["child_boot"]=boot_verify(m2); r9["status"]="PASS" if r9["identity_distinct"] and r9["ancestry_preserved"] and r9["child_boot"]["status"]=="PASS" else "FAIL"
    write_object(m1,"GLOBAL-OBJECT-001","BRAINK regenerative fabric object payload R10","BRAINK::LINEAGE::KEX-MACHINE-001::GENESIS")
    repl=replicate_object(m1,m2)
    offline=Path(str(m1)+".offline");
    if offline.exists(): offline.unlink()
    m1.rename(offline); m2_after_loss=inspect_machine(m2); failover_ok=bool(m2_after_loss["object"]) and m2_after_loss["object"]["obj"]["object_id"]=="GLOBAL-OBJECT-001"
    offline.rename(m1); m1_before=inspect_machine(m1); source=inspect_machine(m2)["object"]["obj"]; reconciled=dict(source); reconciled["replica_of_lineage"]=source["lineage"]; reconciled["lineage"]=m1_before["root"]["obj"]["lineage_root"]; reconciled["state"]="RECONCILED"; fd=os.open(m1,os.O_RDWR); write_block(fd,OBJECT_OFF,reconciled); os.fsync(fd); os.close(fd); m1_after=inspect_machine(m1)
    reconcile_ok=m1_after["object"]["obj"]["payload_sha256"]==m2_after_loss["object"]["obj"]["payload_sha256"] and m1_after["object"]["obj"]["lineage"]!=m2_after_loss["object"]["obj"]["lineage"] and m1_after["object"]["obj"]["object_id"]==m2_after_loss["object"]["obj"]["object_id"]
    r10={"action":"R10_REPLICATION_FAILOVER_RECONCILIATION","machine_1":m1_before["root"]["obj"]["machine_id"],"machine_2":m2_after_loss["root"]["obj"]["machine_id"],"replication":repl,"m1_loss_simulated":True,"m2_failover_read":failover_ok,"m1_restarted":True,"reconciliation_pass":reconcile_ok,"payload_sha256":m2_after_loss["object"]["obj"]["payload_sha256"],"m1_lineage":m1_after["object"]["obj"]["lineage"],"m2_lineage":m2_after_loss["object"]["obj"]["lineage"],"status":"PASS" if repl["payload_sha256_equal"] and repl["lineage_distinct"] and failover_ok and reconcile_ok else "FAIL"}
    Path("/mnt/data/BRAINK_R9_DESCENDANT_RECEIPT.json").write_text(json.dumps(r9,indent=2)); Path("/mnt/data/BRAINK_R10_FABRIC_RECEIPT.json").write_text(json.dumps(r10,indent=2)); print(json.dumps({"R9":r9,"R10":r10},indent=2))

if __name__=="__main__": main()
