#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse


def _readback_hosts() -> set[str]:
    hosts = {"127.0.0.1", "::1", "localhost"}
    tl2 = os.getenv("KEX_TL2_ADDRESS", "").strip()
    if tl2:
        hosts.add(tl2)
    for item in os.getenv("KEX_READBACK_ALLOWLIST", "").split(","):
        item = item.strip()
        if item:
            hosts.add(item)
    return hosts


def _runtime_auth_hosts() -> set[str]:
    # Runtime bearer credentials are more sensitive than readback permission.
    # An allowlisted public observer is not automatically trusted with mutation auth.
    hosts = {"127.0.0.1", "::1", "localhost"}
    tl2 = os.getenv("KEX_TL2_ADDRESS", "").strip()
    if tl2:
        hosts.add(tl2)
    for item in os.getenv("KEX_RUNTIME_AUTH_ALLOWLIST", "").split(","):
        item = item.strip()
        if item:
            hosts.add(item)
    return hosts


def _is_link_local_or_metadata(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_link_local or ip.is_unspecified or ip.is_multicast


def readback_url_allowed(url: str) -> tuple[bool, dict]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, {"reason": "unsupported_or_missing_url_host"}
    host = parsed.hostname
    allowed = _readback_hosts()
    if host in allowed:
        return True, {"host": host, "policy": "EXPLICIT_OR_RUNTIME_SCOPE"}
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except OSError:
        addresses = set()
    if any(_is_link_local_or_metadata(address) for address in addresses):
        return False, {"host": host, "reason": "link_local_or_metadata_destination"}
    return False, {
        "host": host,
        "reason": "destination_not_allowlisted",
        "requiredSetting": "KEX_READBACK_ALLOWLIST",
    }


def runtime_auth_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.hostname and parsed.hostname in _runtime_auth_hosts())
