from fastapi.testclient import TestClient

from runtime.mcp_sdk_environment_server import app


def test_environment_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "runtime://keddeh/mcp-sdk-environment"
    assert payload["environment"] == "environment://keddeh/mcp-sdk"


def test_environment_manifest():
    client = TestClient(app)
    response = client.get("/environment")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mcp"]["endpoint"] == "/mcp"
    assert payload["sdk"]["manifest"] == "/sdk/manifest"


def test_sdk_manifest():
    client = TestClient(app)
    response = client.get("/sdk/manifest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sdk_id"] == "sdk://keddeh/braink"
    assert payload["mcp_endpoint"] == "/mcp"
    assert "BRAINK_MCP_HMAC_KEY_HEX" in payload["configuration"]["required_environment"]
