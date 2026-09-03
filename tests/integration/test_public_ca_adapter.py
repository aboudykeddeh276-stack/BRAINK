from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

import pytest

from enterprise.public_ca_adapter import PublicCAAdapter
from enterprise.tls_authority_runtime import ResidentTLSAuthority


def _openssl() -> str:
    exe = shutil.which("openssl")
    if not exe:
        pytest.skip("openssl unavailable")
    return exe


def _sign_request_with_test_issuer(adapter: PublicCAAdapter, request, tmp_path: Path):
    """Create issuer-returned material for structural verification only.

    ResidentTLSAuthority is used as a deterministic test issuer. This does not prove
    public trust; PublicCAAdapter.external_tls_readback owns that separate boundary.
    """
    openssl = _openssl()
    ca = adapter.resident_tls
    ca.ensure_ca()
    out = tmp_path / "issued"
    out.mkdir()
    cert = out / "certificate.pem"
    chain = out / "chain.pem"
    fullchain = out / "fullchain.pem"
    ext = out / "extensions.cnf"
    sans = [f"DNS:{name}" for name in request.dns_names] + [f"IP:{ip}" for ip in request.ip_addresses]
    ext.write_text(
        "\n".join(
            [
                "basicConstraints=critical,CA:FALSE",
                "keyUsage=critical,digitalSignature,keyEncipherment",
                "extendedKeyUsage=serverAuth",
                "subjectAltName=" + ",".join(sans),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            openssl,
            "x509",
            "-req",
            "-sha256",
            "-in",
            request.csr_path,
            "-CA",
            str(ca.ca_cert),
            "-CAkey",
            str(ca.ca_key),
            "-CAcreateserial",
            "-out",
            str(cert),
            "-days",
            "30",
            "-extfile",
            str(ext),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    chain.write_bytes(ca.ca_cert.read_bytes())
    fullchain.write_bytes(cert.read_bytes() + ca.ca_cert.read_bytes())
    return cert, chain, fullchain


def test_prepare_public_request_is_bound_to_resident_tls_and_sans(tmp_path: Path) -> None:
    tls = ResidentTLSAuthority(tmp_path / "tls")
    adapter = PublicCAAdapter(tls, tmp_path / "public")
    req = adapter.prepare_request(
        "braink.example",
        dns_names=["braink.example", "www.braink.example"],
        ip_addresses=["192.0.2.10"],
    )
    assert req.resident_ca_sha256 == tls.ensure_ca()["ca_cert_sha256"]
    assert set(req.dns_names) == {"braink.example", "www.braink.example"}
    assert req.ip_addresses == ("192.0.2.10",)
    assert Path(req.key_path).is_file() and Path(req.csr_path).is_file()
    text = subprocess.run(
        [_openssl(), "req", "-in", req.csr_path, "-noout", "-text"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode("utf-8", "replace")
    assert "DNS:braink.example" in text
    assert "DNS:www.braink.example" in text
    assert "IP Address:192.0.2.10" in text


def test_issue_fails_closed_without_public_challenge_actuator(tmp_path: Path) -> None:
    tls = ResidentTLSAuthority(tmp_path / "tls")
    adapter = PublicCAAdapter(tls, tmp_path / "public")
    req = adapter.prepare_request("braink.example")
    with pytest.raises(RuntimeError, match="PUBLIC_CA_CHALLENGE_ACTUATOR_UNBOUND"):
        adapter.issue(req)


def test_returned_certificate_must_match_key_sans_and_issuer_chain(tmp_path: Path) -> None:
    tls = ResidentTLSAuthority(tmp_path / "tls")
    adapter = PublicCAAdapter(tls, tmp_path / "public")
    req = adapter.prepare_request(
        "braink.example",
        dns_names=["braink.example", "www.braink.example"],
        ip_addresses=["192.0.2.10"],
    )
    cert, chain, fullchain = _sign_request_with_test_issuer(adapter, req, tmp_path)
    material = adapter.verify_returned_material(req, cert, chain, fullchain)
    assert material.public_key_sha256 == req.public_key_sha256
    assert set(req.dns_names).issubset(set(material.dns_names))
    assert set(req.ip_addresses).issubset(set(material.ip_addresses))

    # Swap in a certificate issued for a different private key. Chain validity alone
    # must not be enough to admit it.
    other = adapter.prepare_request("other.example", dns_names=["other.example"])
    wrong_root = tmp_path / "wrong"
    wrong_root.mkdir()
    wrong_cert, _, _ = _sign_request_with_test_issuer(adapter, other, wrong_root)
    cert.write_bytes(wrong_cert.read_bytes())
    with pytest.raises(RuntimeError, match="PUBLIC_CA_KEY_CERT_MISMATCH"):
        adapter.verify_returned_material(req, cert, chain, fullchain)
