from __future__ import annotations
from pathlib import Path
import json, sqlite3, time, uuid

from .service_fabric_r24 import MarketServiceFabric, sha


class LiveMarketServiceFabric(MarketServiceFabric):
    """R25 binds the usable R24 service fabric to observed connector resources."""

    def __init__(self, db_path: str | Path, infrastructure_path: str | Path | None = None):
        super().__init__(db_path)
        self.infrastructure_path = Path(infrastructure_path or Path(__file__).with_name("LIVE_INFRASTRUCTURE_R25.json"))
        self._init_live()

    def _init_live(self):
        d = self.db()
        d.executescript("""
        CREATE TABLE IF NOT EXISTS external_resources(
          resource_id TEXT PRIMARY KEY,
          service TEXT NOT NULL,
          provider TEXT NOT NULL,
          external_ref TEXT NOT NULL,
          state TEXT NOT NULL,
          metadata TEXT NOT NULL,
          bound_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS service_instances(
          instance_id TEXT PRIMARY KEY,
          business_id TEXT NOT NULL,
          service TEXT NOT NULL,
          resource_id TEXT NOT NULL,
          state TEXT NOT NULL,
          created_ns INTEGER NOT NULL
        );
        """)
        d.commit(); d.close()

    def bind_observed_infrastructure(self):
        infra = json.loads(self.infrastructure_path.read_text())
        resources = []
        drive = infra["drive"]
        for service, key in {
            "runtime_bindings":"runtime_bindings_folder",
            "services":"services_folder",
            "customer_file_base":"customer_file_base_folder",
            "workspaces":"workspaces_folder",
            "publishing":"publishing_folder",
            "research_illlm":"research_illlm_folder",
            "server_rooms":"server_rooms_folder",
        }.items():
            resources.append(self.bind_external_resource(service,"Google Drive",drive[key],"BOUND_WRITE",{"kind":"folder"}))
        for service, key in {
            "runtime_mail":"runtime_mail_label",
            "customer_services_mail":"customer_services_label",
            "publishing_mail":"publishing_label",
            "runtime_alerts_mail":"runtime_alerts_label",
        }.items():
            resources.append(self.bind_external_resource(service,"Gmail",infra["gmail"][key],"BOUND_CONTROL_PLANE",{"kind":"label"}))
        return resources

    def bind_external_resource(self, service, provider, external_ref, state, metadata=None):
        rid = "EXT-" + sha({"service":service,"provider":provider,"external_ref":external_ref})[:16]
        now = time.time_ns(); meta = json.dumps(metadata or {},sort_keys=True)
        d = self.db()
        d.execute("INSERT OR REPLACE INTO external_resources VALUES(?,?,?,?,?,?,?)",
                  (rid,service,provider,external_ref,state,meta,now))
        d.commit(); d.close()
        self.receipt("bind_external_resource",rid,"PASS",{"service":service,"provider":provider,"external_ref":external_ref,"state":state})
        return {"resource_id":rid,"service":service,"provider":provider,"external_ref":external_ref,"state":state}

    def resolve_resource(self, service):
        d=self.db(); row=d.execute("SELECT * FROM external_resources WHERE service=? ORDER BY bound_ns DESC LIMIT 1",(service,)).fetchone(); d.close()
        return dict(row) if row else None

    def create_service_instance(self,business_id,service):
        resource=self.resolve_resource(service)
        if not resource:
            return {"state":"HELD_RESOURCE_HOLE","business_id":business_id,"service":service}
        iid="SVC-"+uuid.uuid4().hex[:12]; now=time.time_ns(); d=self.db()
        d.execute("INSERT INTO service_instances VALUES(?,?,?,?,?,?)",(iid,business_id,service,resource["resource_id"],"ACTIVE",now)); d.commit(); d.close()
        return {"instance_id":iid,"business_id":business_id,"service":service,"resource_id":resource["resource_id"],"state":"ACTIVE","receipt":self.receipt("create_service_instance",iid,"PASS",{"business_id":business_id,"service":service,"resource_id":resource["resource_id"]})}

    def live_metrics(self):
        base=self.metrics(); d=self.db()
        base["external_resources"]=d.execute("SELECT COUNT(*) FROM external_resources").fetchone()[0]
        base["service_instances"]=d.execute("SELECT COUNT(*) FROM service_instances").fetchone()[0]
        d.close(); base["live_state_root"]=sha(base); return base
