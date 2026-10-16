import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from runtime.public_gateway import Handler


def test_network_ingress_is_bound_to_real_http_socket():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        with urllib.request.urlopen(
            f"http://{host}:{port}/network/ingress",
            timeout=5,
        ) as response:
            assert response.status == 200
            payload = json.load(response)

        assert payload["logical_requirement"] == "required://network/ingress"
        assert payload["binding_state"] == "BOUND_LOCAL_OBSERVATION"
        assert payload["carrier_role"] == "PROJECTION_ONLY"
        assert payload["socket"]["local"][0] in {"127.0.0.1", "::1"}
        assert payload["socket"]["remote"][0] in {"127.0.0.1", "::1"}
        assert payload["external_proof"] == "UNPROVEN"
        assert payload["public_dns"] == "UNPROVEN"
        assert payload["public_tls"] == "UNPROVEN"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
