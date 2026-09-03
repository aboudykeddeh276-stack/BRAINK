from __future__ import annotations

import socket
import threading
import time

import pytest

from enterprise.tls_authority_runtime import ResidentTLSAuthority


def test_tls_authority_persists_and_reads_back(tmp_path):
    auth = ResidentTLSAuthority(tmp_path / "tls")
    ca = auth.ensure_ca()
    material = auth.issue_server_certificate(
        "localhost",
        dns_names=["localhost"],
        ip_addresses=["127.0.0.1"],
        days=30,
    )
    assert ca["authority"] == "BRAINK_LOCAL_TLS_AUTHORITY"
    assert material.cert_sha256
    assert auth.verify_chain(material)

    # Recreate the controller to prove process lifetime is not authority lifetime.
    restored = ResidentTLSAuthority(tmp_path / "tls")
    rb = restored.readback(material.certificate_id)
    assert rb.cert_sha256 == material.cert_sha256
    assert rb.public_key_sha256 == material.public_key_sha256
    assert restored.authority_state()["certificate_count"] == 1


def test_tls_readback_detects_material_tampering(tmp_path):
    auth = ResidentTLSAuthority(tmp_path / "tls")
    material = auth.issue_server_certificate("localhost", dns_names=["localhost"], days=30)
    cert = __import__("pathlib").Path(material.cert_path)
    cert.write_bytes(cert.read_bytes() + b"\nTAMPERED\n")
    with pytest.raises(RuntimeError, match="TLS_READBACK_MISMATCH|TLS_CHAIN_READBACK_FAILED"):
        auth.readback(material.certificate_id)


def test_tls_renewal_uses_persisted_authority(tmp_path):
    auth = ResidentTLSAuthority(tmp_path / "tls")
    old = auth.issue_server_certificate("localhost", dns_names=["localhost"], days=1)
    renewed = auth.renew_if_needed(old.certificate_id, renew_before_seconds=2 * 24 * 3600, days=30)
    assert renewed.certificate_id != old.certificate_id
    assert renewed.cert_sha256 != old.cert_sha256
    assert auth.verify_chain(renewed)
    assert auth.authority_state()["certificate_count"] == 2


def test_real_tls_client_server_handshake_uses_resident_ca(tmp_path):
    auth = ResidentTLSAuthority(tmp_path / "tls")
    material = auth.issue_server_certificate(
        "localhost",
        dns_names=["localhost"],
        ip_addresses=["127.0.0.1"],
        days=30,
    )
    server_context = auth.server_context(material.certificate_id)
    client_context = auth.client_context()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    host, port = listener.getsockname()
    result: dict[str, object] = {}

    def serve() -> None:
        try:
            conn, _ = listener.accept()
            with conn:
                with server_context.wrap_socket(conn, server_side=True) as tls:
                    request = tls.recv(16)
                    result["request"] = request
                    result["version"] = tls.version()
                    tls.sendall(b"BRAINK-TLS-OK")
        except BaseException as exc:  # propagate thread failure to test
            result["error"] = exc
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    with socket.create_connection((host, port), timeout=5) as raw:
        with client_context.wrap_socket(raw, server_hostname="localhost") as tls:
            tls.sendall(b"PING")
            response = tls.recv(64)
            peer = tls.getpeercert()
            assert response == b"BRAINK-TLS-OK"
            assert tls.version() in {"TLSv1.2", "TLSv1.3"}
            assert peer

    thread.join(timeout=5)
    assert not thread.is_alive()
    assert "error" not in result
    assert result["request"] == b"PING"
    assert result["version"] in {"TLSv1.2", "TLSv1.3"}
