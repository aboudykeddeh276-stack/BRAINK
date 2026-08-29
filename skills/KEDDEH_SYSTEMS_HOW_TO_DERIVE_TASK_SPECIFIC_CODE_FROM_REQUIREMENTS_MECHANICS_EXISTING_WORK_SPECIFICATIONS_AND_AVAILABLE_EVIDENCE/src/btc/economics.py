"""Mechanic: economic accounting — block subsidy and coinbase value."""

from __future__ import annotations

COIN = 100_000_000  # satoshis per BTC
_INITIAL_SUBSIDY = 50 * COIN
_HALVING_INTERVAL = 210_000


def block_subsidy(height: int) -> int:
    """The block subsidy in satoshis at a given height (Bitcoin halving schedule)."""
    if height < 0:
        raise ValueError("height must be non-negative")
    halvings = height // _HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return _INITIAL_SUBSIDY >> halvings


def coinbase_value(height: int, total_fees: int) -> int:
    """Total coinbase output value = subsidy + collected fees (conservative)."""
    if total_fees < 0:
        raise ValueError("total_fees must be non-negative")
    return block_subsidy(height) + total_fees
