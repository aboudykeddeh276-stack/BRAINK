from __future__ import annotations

"""Public certificate authority adapter beneath BRAINK/KEX TLS_ROOT.

This module deliberately does not define TLS identity.  It consumes resident TLS
state and projects a certificate request into a configured public CA/ACME carrier.
The public CA is therefore an authority adapter, not the source of BRAINK state.

Execution contract:
    TLS_ROOT resident authority
      -> SAN-bound key/CSR
      -> configured domain-control challenge actuator
      -> ACME client/public CA
      -> returned certificate/chain
      -> key + SAN + trust verification
      -> public certificate receipt

No challenge actuator or no ACME client means BLOCKED, not "issued".
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import ipaddress
import json
import os
import shutil
import ssl
import subprocess
import time

from enterprise.tls_authority_runtime import ResidentTLSAuthority

SCHEMA = "braink.kex.public-ca-adapter.v1"


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(argv: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


@dataclass(frozen=True)
class PublicCertificateRequest:
    request_id: str
    common_name: str
    dns_names: tuple[str, ...]
    ip_addresses: tuple[str, ...]
    key_path: str
    csr_path: str
    csr_sha256: str
    public_key_sha256: str
    resident_ca_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, **asdict(self)}


@dataclass(frozen=True)
class PublicCertificateMaterial:
    request_id: str
    certificate_path: str
    chain_path: str
    fullchain_path: str
    private_key_path: str
    certificate_sha256: str
    public_key_sha256: str
    dns_names: tuple[str, ...]
    ip_addresses: tuple[str, ...]
    issued_ns: int
    provider: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, **asdict(self)}


class PublicCAAdapter:
    """Fail-closed public CA adapter consuming a ResidentTLSAuthority.

    `challenge_auth_hook` and `challenge_cleanup_hook` are executable files owned by
    the domain authority layer.  For DNS-01 they must publish/remove the exact TXT
    challenge on the *publicly authoritative* DNS path.  This adapter never assumes
    that the resident/private registrar is publicly delegated.
    """

    def __init__(
        self,
        resident_tls: ResidentTLSAuthority,
        state_root: str | Path,
        *,
        certbot_binary: str = "certbot",
        challenge_auth_hook: str | Path | None = None,
        challenge_cleanup_hook: str | Path | None = None,
        directory_url: str | None = None,
        email: str | None = None,
    ) -> None:
        self.resident_tls = resident_tls
        self.root = Path(state_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.request_root = self.root / "requests"
        self.issued_root = self.root / "issued"
        self.request_root.mkdir(exist_ok=True)
        self.issued_root.mkdir(exist_ok=True)
        self.certbot_binary = certbot_binary
        self.challenge_auth_hook = Path(challenge_auth_hook).resolve() if challenge_auth_hook else None
        self.challenge_cleanup_hook = Path(challenge_cleanup_hook).resolve() if challenge_cleanup_hook else None
        self.directory_url = directory_url
        self.email = email
        self.receipts = self.root / "public-ca-receipts.jsonl"

    def _receipt(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "schema": SCHEMA,
            "event": event,
            "created_ns": time.time_ns(),
            "payload": payload,
            "payload_sha256": _sha(_canon(payload)),
        }
        with self.receipts.open("a", encoding="utf-8") as fh:
            fh.write(_canon(record).decode("utf-8") + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _validate_hooks(self) -> None:
        if not self.challenge_auth_hook or not self.challenge_cleanup_hook:
            raise RuntimeError("PUBLIC_CA_CHALLENGE_ACTUATOR_UNBOUND")
        for hook in (self.challenge_auth_hook, self.challenge_cleanup_hook):
            if not hook.is_file() or not os.access(hook, os.X_OK):
                raise RuntimeError(f"PUBLIC_CA_CHALLENGE_ACTUATOR_NOT_EXECUTABLE:{hook}")

    def _certbot(self) -> str:
        resolved = shutil.which(self.certbot_binary)
        if not resolved:
            raise RuntimeError("PUBLIC_CA_ACME_CLIENT_UNAVAILABLE")
        return resolved

    def prepare_request(
        self,
        common_name: str,
        *,
        dns_names: list[str] | None = None,
        ip_addresses: list[str] | None = None,
    ) -> PublicCertificateRequest:
        ca = self.resident_tls.ensure_ca()
        dns = tuple(dict.fromkeys(dns_names or [common_name]))
        ips = tuple(str(ipaddress.ip_address(v)) for v in dict.fromkeys(ip_addresses or []))
        seed = _canon({"cn": common_name, "dns": dns, "ip": ips, "ns": time.time_ns()})
        request_id = "PUBLIC-TLS-" + _sha(seed)[:24]
        directory = self.request_root / request_id
        directory.mkdir(parents=True, exist_ok=False)
        key = directory / "private-key.pem"
        csr = directory / "request.csr.pem"
        openssl = shutil.which("openssl")
        if not openssl:
            raise RuntimeError("OPENSSL_NOT_AVAILABLE")
        _run([openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)])
        os.chmod(key, 0o600)
        sans = [f"DNS:{name}" for name in dns] + [f"IP:{ip}" for ip in ips]
        argv = [openssl, "req", "-new", "-sha256", "-key", str(key), "-out", str(csr), "-subj", f"/CN={common_name}"]
        if sans:
            argv += ["-addext", "subjectAltName=" + ",".join(sans)]
        _run(argv)
        pub = _run([openssl, "pkey", "-in", str(key), "-pubout"]).stdout
        request = PublicCertificateRequest(
            request_id=request_id,
            common_name=common_name,
            dns_names=dns,
            ip_addresses=ips,
            key_path=str(key),
            csr_path=str(csr),
            csr_sha256=_sha(csr.read_bytes()),
            public_key_sha256=_sha(pub),
            resident_ca_sha256=ca["ca_cert_sha256"],
        )
        self._receipt("PUBLIC_CSR_PREPARED", request.as_dict())
        return request

    def _certificate_sans(self, certificate: Path) -> tuple[set[str], set[str]]:
        openssl = shutil.which("openssl") or "openssl"
        proc = _run([openssl, "x509", "-in", str(certificate), "-noout", "-ext", "subjectAltName"])
        text = proc.stdout.decode("utf-8", "replace")
        dns: set[str] = set()
        ips: set[str] = set()
        for token in text.replace("\n", ",").split(","):
            token = token.strip()
            if token.startswith("DNS:"):
                dns.add(token[4:].strip())
            elif token.startswith("IP Address:"):
                ips.add(str(ipaddress.ip_address(token.split(":", 1)[1].strip())))
        return dns, ips

    def verify_returned_material(
        self,
        request: PublicCertificateRequest,
        certificate: Path,
        chain: Path,
        fullchain: Path,
    ) -> PublicCertificateMaterial:
        for path in (certificate, chain, fullchain, Path(request.key_path)):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"PUBLIC_CA_MATERIAL_MISSING:{path}")
        openssl = shutil.which("openssl") or "openssl"
        cert_pub = _run([openssl, "x509", "-in", str(certificate), "-pubkey", "-noout"]).stdout
        key_pub = _run([openssl, "pkey", "-in", request.key_path, "-pubout"]).stdout
        if _sha(cert_pub) != _sha(key_pub) or _sha(key_pub) != request.public_key_sha256:
            raise RuntimeError("PUBLIC_CA_KEY_CERT_MISMATCH")
        observed_dns, observed_ips = self._certificate_sans(certificate)
        if not set(request.dns_names).issubset(observed_dns):
            raise RuntimeError(f"PUBLIC_CA_DNS_SAN_MISMATCH:{sorted(set(request.dns_names)-observed_dns)}")
        if not set(request.ip_addresses).issubset(observed_ips):
            raise RuntimeError(f"PUBLIC_CA_IP_SAN_MISMATCH:{sorted(set(request.ip_addresses)-observed_ips)}")
        # Verify the leaf through the supplied issuer chain. This establishes that the
        # returned material is internally chain-valid. External endpoint readback below
        # remains the authoritative public-trust check using the host trust store.
        verify = subprocess.run(
            [openssl, "verify", "-untrusted", str(chain), str(certificate)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if verify.returncode != 0:
            raise RuntimeError("PUBLIC_CA_RETURNED_CHAIN_INVALID:" + verify.stderr.decode("utf-8", "replace"))
        material = PublicCertificateMaterial(
            request_id=request.request_id,
            certificate_path=str(certificate),
            chain_path=str(chain),
            fullchain_path=str(fullchain),
            private_key_path=request.key_path,
            certificate_sha256=_sha(certificate.read_bytes()),
            public_key_sha256=request.public_key_sha256,
            dns_names=tuple(sorted(observed_dns)),
            ip_addresses=tuple(sorted(observed_ips)),
            issued_ns=time.time_ns(),
            provider="ACME_CERTBOT",
        )
        self._receipt("PUBLIC_CERTIFICATE_VERIFIED", material.as_dict())
        return material

    def issue(self, request: PublicCertificateRequest) -> PublicCertificateMaterial:
        self._validate_hooks()
        certbot = self._certbot()
        out = self.issued_root / request.request_id
        out.mkdir(parents=True, exist_ok=False)
        cert = out / "certificate.pem"
        chain = out / "chain.pem"
        fullchain = out / "fullchain.pem"
        argv = [
            certbot,
            "certonly",
            "--manual",
            "--non-interactive",
            "--preferred-challenges",
            "dns",
            "--manual-auth-hook",
            str(self.challenge_auth_hook),
            "--manual-cleanup-hook",
            str(self.challenge_cleanup_hook),
            "--csr",
            request.csr_path,
            "--cert-path",
            str(cert),
            "--chain-path",
            str(chain),
            "--fullchain-path",
            str(fullchain),
        ]
        if self.directory_url:
            argv += ["--server", self.directory_url]
        if self.email:
            argv += ["--email", self.email, "--agree-tos"]
        else:
            argv += ["--register-unsafely-without-email"]
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        execution = {
            "request_id": request.request_id,
            "returncode": proc.returncode,
            "stdout_sha256": _sha(proc.stdout),
            "stderr_sha256": _sha(proc.stderr),
            "directory_url": self.directory_url,
        }
        self._receipt("PUBLIC_CA_EXECUTION", execution)
        if proc.returncode != 0:
            raise RuntimeError("PUBLIC_CA_ISSUANCE_FAILED:" + proc.stderr.decode("utf-8", "replace")[-4000:])
        return self.verify_returned_material(request, cert, chain, fullchain)

    @staticmethod
    def external_tls_readback(hostname: str, *, port: int = 443, timeout: float = 8.0) -> dict[str, Any]:
        """Perform hostname-verifying readback through the system public trust store."""
        import socket
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as tls:
                peer = tls.getpeercert(binary_form=True)
                decoded = tls.getpeercert()
                if not peer or not decoded:
                    raise RuntimeError("PUBLIC_TLS_PEER_CERTIFICATE_MISSING")
                return {
                    "schema": SCHEMA,
                    "hostname": hostname,
                    "port": port,
                    "tls_version": tls.version(),
                    "cipher": tls.cipher(),
                    "certificate_sha256": _sha(peer),
                    "peer": decoded,
                    "readback_ns": time.time_ns(),
                    "verification": "SYSTEM_TRUST_AND_HOSTNAME_VERIFIED",
                }
