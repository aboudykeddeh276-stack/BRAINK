from __future__ import annotations

import tempfile
from pathlib import Path

from mcp.braink_process_adapter.system_surface import ModelResidencyManager


class FakeVFS:
    def __init__(self):
        self.bound = {}

    def bind(self, logical: str, backing: str):
        self.bound[logical] = backing
        return {"status": "BOUND", "logical": logical, "backing": backing}

    def read(self, logical: str, backing: str):
        if self.bound.get(logical) != backing:
            return {"status": "NOT_BOUND"}
        return {
            "bind": {"status": "BOUND", "logical": logical, "backing": backing},
            "readback": {"status": "PASS", "logical": logical},
        }


class FakeILLLM:
    def __init__(self):
        self.bound = {}

    def bind_model(self, node_id: str, descriptor: dict):
        self.bound[(node_id, descriptor["model_id"])] = dict(descriptor)
        return {"status": "BOUND", "node_id": node_id, "model_id": descriptor["model_id"]}

    def read_model(self, node_id: str, model_id: str):
        if (node_id, model_id) not in self.bound:
            return {"status": "UNBOUND"}
        return {"status": "PASS", "node_id": node_id, "model_id": model_id}


class UnboundILLLM:
    def bind_model(self, node_id: str, descriptor: dict):
        return {"status": "UNBOUND_RUNTIME_PATH"}

    def read_model(self, node_id: str, model_id: str):
        return {"status": "UNBOUND_RUNTIME_PATH"}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="braink-r8-system-surface-") as td:
        root = Path(td)
        model = root / "model"
        model.mkdir()
        (model / "config.json").write_text('{"model":"fixture"}\n', encoding="utf-8")
        (model / "weights-00001.safetensors").write_bytes(b"fixture-weight-bytes")

        manager = ModelResidencyManager(root / "state", FakeVFS(), FakeILLLM())
        registered = manager.register_model(
            "fixture-model",
            str(model),
            capabilities={"code": True, "planning": True},
        )
        assert registered["status"] == "REGISTERED"
        assert registered["model"]["total_bytes"] > 0
        assert len(registered["model"]["content_root"]) == 64

        node = manager.bootstrap_node(
            "NODE-R8-1",
            {"fixture-model": {}},
            {"BRAINK-CODE": ["fixture-model"], "BRAINK-SYSTEM": ["fixture-model"]},
        )
        assert node["status"] == "READY", node
        assert node["bindings"]["fixture-model"]["physical"]["status"] == "PRESENT"

        readiness = manager.readiness("NODE-R8-1")
        assert readiness["status"] == "READY", readiness
        assert readiness["agent_authorities"]["BRAINK-CODE"] == ["fixture-model"]

        manifest = manager.system_manifest()
        assert manifest["external_surface"]["protocol"] == "MCP"
        assert manifest["external_surface"]["authority"] == "PROJECTION_AND_INVOCATION_ONLY"
        assert "IL_LLM" in manifest["loadout"]
        assert "MCP != BRAINK authority" in manifest["non_equivalence"]

        # Physical bytes disappearing must invalidate readiness.
        (model / "weights-00001.safetensors").unlink()
        drifted = manager.readiness("NODE-R8-1")
        assert drifted["status"] == "NOT_READY"
        assert drifted["checks"]["fixture-model"]["physical"]["status"] == "DRIFTED"

    with tempfile.TemporaryDirectory(prefix="braink-r8-unbound-illlm-") as td:
        root = Path(td)
        model = root / "model.bin"
        model.write_bytes(b"real-bytes")
        manager = ModelResidencyManager(root / "state", FakeVFS(), UnboundILLLM())
        manager.register_model("fixture-model", str(model), model_format="binary")
        node = manager.bootstrap_node(
            "NODE-R8-2",
            {"fixture-model": {}},
            {"BRAINK-CODE": ["fixture-model"]},
        )
        assert node["status"] == "NOT_READY"
        assert node["bindings"]["fixture-model"]["illlm"]["status"] == "UNBOUND_RUNTIME_PATH"

    print("R8_MCP_SYSTEM_SURFACE_PASS")


if __name__ == "__main__":
    main()
