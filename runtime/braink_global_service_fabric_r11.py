from pathlib import Path
import json, hashlib, os

BLOCK = 4096
SUPER_OFF = 0
BRAINK_OFF = 256 * BLOCK
SERVICE_OFF = 768 * BLOCK
ZEROLESS = [-3,-2,1,2,3]

def sha(b): return hashlib.sha256(b).hexdigest()

def write_block(fd, off, obj):
    raw = json.dumps(obj, sort_keys=True, separators=(",",":")).encode()
    if len(raw) > BLOCK - 8:
        raise RuntimeError("E_BLOCK_TOO_LARGE")
    buf = bytearray(BLOCK)
    buf[:4] = len(raw).to_bytes(4, "big")
    buf[8:8+len(raw)] = raw
    os.pwrite(fd, bytes(buf), off)
    return sha(raw)

def read_block(fd, off):
    head = os.pread(fd, 8, off)
    if len(head) < 8:
        return None
    n = int.from_bytes(head[:4], "big")
    if n <= 0 or n > BLOCK - 8:
        return None
    raw = os.pread(fd, n, off+8)
    return {"obj": json.loads(raw.decode()), "raw": raw, "sha256": sha(raw)}

def inspect_machine(path):
    fd = os.open(path, os.O_RDONLY)
    s = read_block(fd, SUPER_OFF)
    r = read_block(fd, BRAINK_OFF)
    f = read_block(fd, SERVICE_OFF)
    os.close(fd)
    return {"super":s, "root":r, "fabric":f}

def build_service_fabric(machine):
    root = machine["root"]["obj"]
    mid = root["machine_id"]
    bid = root["braink_id"]
    lineage = root["lineage_root"]

    services = {
        "SERVER_ROOT": {
            "type":"SERVER_ROOT",
            "lexical_id":f"LEX://SERVER/{mid}/GLOBAL",
            "vector_id":f"VEC://{mid}/SERVER/LOCAL",
            "route_id":f"KEX://MACHINE/{mid}/SERVER/",
            "adapter":"BRAINK_SERVER_ADAPTER_R11",
            "carrier":"HTTP/TCP/IPv4",
        },
        "DOMAIN_ROOT": {
            "type":"DOMAIN_ROOT",
            "lexical_id":"LEX://DOMAIN/keddeh.com",
            "vector_id":f"VEC://{mid}/DOMAIN/keddeh.com",
            "route_id":f"KEX://MACHINE/{mid}/DOMAIN/keddeh.com/",
            "adapter":"BRAINK_DOMAIN_ADAPTER_R11",
            "domain_name":"keddeh.com",
        },
        "DNS_ROOT": {
            "type":"DNS_ROOT",
            "lexical_id":"LEX://DNS/keddeh.com",
            "vector_id":f"VEC://{mid}/DNS/keddeh.com",
            "route_id":f"KEX://MACHINE/{mid}/DNS/keddeh.com/",
            "adapter":"BRAINK_DNS_ADAPTER_R11",
            "authority_state":"INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY",
        },
        "REGISTRAR_ROOT": {
            "type":"REGISTRAR_ROOT",
            "lexical_id":"LEX://REGISTRAR/keddeh.com",
            "vector_id":f"VEC://{mid}/REGISTRAR/keddeh.com",
            "route_id":f"KEX://MACHINE/{mid}/REGISTRAR/keddeh.com/",
            "adapter":"BRAINK_REGISTRAR_ADAPTER_R11",
            "authority_state":"INTERNAL_RESIDENT_NOT_REGISTRY_AUTHORITY",
        },
        "TLS_ROOT": {
            "type":"TLS_ROOT",
            "lexical_id":"LEX://TLS/keddeh.com",
            "vector_id":f"VEC://{mid}/TLS/keddeh.com",
            "route_id":f"KEX://MACHINE/{mid}/TLS/keddeh.com/",
            "adapter":"BRAINK_TLS_ADAPTER_R11",
            "authority_state":"INTERNAL_RESIDENT_NOT_CA_ISSUED",
        },
        "CLOUD_ROOT": {
            "type":"CLOUD_ROOT",
            "lexical_id":"LEX://CLOUD/BRAINK/GLOBAL",
            "vector_id":f"VEC://{mid}/CLOUD/LOCAL",
            "route_id":f"KEX://MACHINE/{mid}/CLOUD/",
            "adapter":"BRAINK_CLOUD_ADAPTER_R11",
            "replication_policy":"TWO_MACHINE_CANONICAL_OBJECT_REPLICATION",
        },
    }

    fabric = {
        "schema":"braink.global-service-fabric.r11",
        "machine_id":mid,
        "braink_id":bid,
        "lineage_root":lineage,
        "vfs_role":"RESOLVER_ONLY",
        "medium_root":root["medium_root"],
        "controller_root":root["controller_root"],
        "services":services,
        "state":"RESIDENT",
    }
    return fabric

def install_fabric(path):
    m = inspect_machine(path)
    fabric = build_service_fabric(m)
    fd = os.open(path, os.O_RDWR)
    digest = write_block(fd, SERVICE_OFF, fabric)
    os.fsync(fd); os.close(fd)
    return {"fabric":fabric,"sha256":digest}

def verify_fabric(path):
    m = inspect_machine(path)
    f = m["fabric"]
    if not f:
        return {"status":"FAIL","reason":"MISSING_FABRIC"}
    obj = f["obj"]
    required = ["SERVER_ROOT","DOMAIN_ROOT","DNS_ROOT","REGISTRAR_ROOT","TLS_ROOT","CLOUD_ROOT"]
    checks = {
        "state_valid": obj.get("state") in {"RESIDENT","RECONCILED"},
        "vfs_resolver_only": obj.get("vfs_role") == "RESOLVER_ONLY",
        "machine_match": obj.get("machine_id") == m["root"]["obj"]["machine_id"],
        "braink_match": obj.get("braink_id") == m["root"]["obj"]["braink_id"],
        "lineage_match": obj.get("lineage_root") == m["root"]["obj"]["lineage_root"],
        "all_roots_present": all(k in obj.get("services",{}) for k in required),
        "domain_bound": obj["services"]["DOMAIN_ROOT"].get("domain_name") == "keddeh.com",
        "dns_not_overpromoted": obj["services"]["DNS_ROOT"].get("authority_state") == "INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY",
        "registrar_not_overpromoted": obj["services"]["REGISTRAR_ROOT"].get("authority_state") == "INTERNAL_RESIDENT_NOT_REGISTRY_AUTHORITY",
        "tls_not_overpromoted": obj["services"]["TLS_ROOT"].get("authority_state") == "INTERNAL_RESIDENT_NOT_CA_ISSUED",
    }
    return {"status":"PASS" if all(checks.values()) else "FAIL","checks":checks,"fabric_sha256":f["sha256"],"fabric":obj}

def replicate_canonical_service_state(src, dst):
    sm = inspect_machine(src)
    dm = inspect_machine(dst)
    sf = sm["fabric"]["obj"]
    df = dm["fabric"]["obj"]
    for key, svc in sf["services"].items():
        target = dict(svc)
        target["vector_id"] = df["services"][key]["vector_id"]
        target["route_id"] = df["services"][key]["route_id"]
        df["services"][key] = target
    df["replica_of_lineage"] = sf["lineage_root"]
    df["lineage_root"] = dm["root"]["obj"]["lineage_root"]
    fd = os.open(dst, os.O_RDWR)
    digest = write_block(fd, SERVICE_OFF, df)
    os.fsync(fd); os.close(fd)

    src_after = inspect_machine(src)["fabric"]["obj"]
    dst_after = inspect_machine(dst)["fabric"]["obj"]
    canonical_fields = ["lexical_id","type","adapter"]
    same = True
    for key in src_after["services"]:
        for field in canonical_fields:
            same = same and (src_after["services"][key].get(field) == dst_after["services"][key].get(field))
    return {
        "canonical_service_identity_equal": same,
        "lineage_distinct": src_after["lineage_root"] != dst_after["lineage_root"],
        "vector_routes_distinct": all(
            src_after["services"][k]["vector_id"] != dst_after["services"][k]["vector_id"]
            for k in src_after["services"]
        ),
        "replica_digest": digest,
    }

def main():
    m1 = Path("/mnt/data/BRAINK_MACHINE_001_R9.vdisk")
    m2 = Path("/mnt/data/BRAINK_MACHINE_002_R9.vdisk")

    install_fabric(m1)
    install_fabric(m2)
    v1 = verify_fabric(m1)
    v2 = verify_fabric(m2)
    repl = replicate_canonical_service_state(m1, m2)

    offline = Path(str(m1)+".offline_r11")
    if offline.exists():
        offline.unlink()
    m1.rename(offline)
    m2_live = verify_fabric(m2)
    failover = (
        m2_live["status"] == "PASS"
        and len(m2_live["fabric"]["services"]) == 6
        and m2_live["fabric"]["services"]["DOMAIN_ROOT"]["lexical_id"] == "LEX://DOMAIN/keddeh.com"
    )

    offline.rename(m1)
    m1_pre = inspect_machine(m1)["fabric"]["obj"]
    m2_state = inspect_machine(m2)["fabric"]["obj"]
    reconciled = dict(m1_pre)
    for key, svc in m2_state["services"].items():
        merged = dict(svc)
        merged["vector_id"] = m1_pre["services"][key]["vector_id"]
        merged["route_id"] = m1_pre["services"][key]["route_id"]
        reconciled["services"][key] = merged
    reconciled["lineage_root"] = inspect_machine(m1)["root"]["obj"]["lineage_root"]
    reconciled["state"] = "RECONCILED"
    fd = os.open(m1, os.O_RDWR)
    write_block(fd, SERVICE_OFF, reconciled)
    os.fsync(fd); os.close(fd)
    vr = verify_fabric(m1)

    receipt = {
        "schema":"braink.global-service-fabric.r11.receipt",
        "machine_1":v1["fabric"]["machine_id"],
        "machine_2":v2["fabric"]["machine_id"],
        "roots":["SERVER_ROOT","DOMAIN_ROOT","DNS_ROOT","REGISTRAR_ROOT","TLS_ROOT","CLOUD_ROOT"],
        "machine_1_install_verify":v1["status"],
        "machine_2_install_verify":v2["status"],
        "replication":repl,
        "secondary_available_during_primary_unavailability":failover,
        "primary_reconciliation_verify":vr["status"],
        "external_authority_claims":{
            "public_dns":"NOT_PROVEN",
            "registry_registrar_authority":"NOT_PROVEN",
            "ca_tls_issuance":"NOT_PROVEN",
            "wan_multi_host":"NOT_PROVEN",
        },
        "status":"PASS" if (
            v1["status"]=="PASS" and v2["status"]=="PASS"
            and repl["canonical_service_identity_equal"]
            and repl["lineage_distinct"]
            and repl["vector_routes_distinct"]
            and failover
            and vr["status"]=="PASS"
        ) else "FAIL"
    }
    Path("/mnt/data/BRAINK_R11_GLOBAL_SERVICE_FABRIC_RECEIPT.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))

if __name__ == "__main__":
    main()
