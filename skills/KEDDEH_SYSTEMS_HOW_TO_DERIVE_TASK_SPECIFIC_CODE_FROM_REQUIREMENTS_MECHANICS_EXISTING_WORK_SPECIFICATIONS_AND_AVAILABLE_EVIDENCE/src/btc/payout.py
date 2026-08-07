"""Mechanic: payout scriptPubKey derivation for the coinbase.

Two authoritative pathways, both keeping private-key material inside the control
plane and OUT of the hashing hardware:

  * ``payout_script_from_address``: decode a configured mainnet address into its
    output script (no wallet, no keys involved at all).
  * ``payout_script_from_wallet``: ask the node's private wallet RPC for a fresh
    address, then resolve its scriptPubKey via ``getaddressinfo``.

Once the script is derived, ``coinbase.py`` consumes it. Hashing workers only ever
see the resulting job, never the wallet or keys.
"""

from __future__ import annotations

from .address import address_to_script
from .rpc import CoreRpcClient


def payout_script_from_address(address: str) -> bytes:
    """Derive the coinbase payout script from a static configured address."""
    return address_to_script(address)


def payout_script_from_wallet(
    client: CoreRpcClient, label: str = "keddeh-coinbase", address_type: str = "bech32"
) -> tuple[str, bytes]:
    """Derive a fresh payout script from the node's private wallet RPC.

    Returns ``(address, script_pubkey_bytes)``. Prefers the authoritative
    ``scriptPubKey`` reported by ``getaddressinfo``; falls back to decoding the
    address locally if the node omits it.
    """
    address = client.getnewaddress(label, address_type)
    info = client.getaddressinfo(address)
    script_hex = info.get("scriptPubKey")
    if script_hex:
        return address, bytes.fromhex(script_hex)
    return address, address_to_script(address)
