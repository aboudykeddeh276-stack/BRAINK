"""Mechanic: revenue / cost profitability telemetry.

Turns observed execution (measured hashrate) and live network parameters (the
template target) into an expectation of revenue and cost. The probability that a
single SHA256d trial produces a valid block is ``target / 2**256``; the expected
blocks/second is that probability times the hashrate.

This is measurement, not assertion: feed it the *measured* hashrate from
``measure.py`` and the *real* nBits from the live template.
"""

from __future__ import annotations

from dataclasses import dataclass

from .economics import COIN, coinbase_value
from .target import bits_to_target

_HASH_SPACE = 1 << 256
_SECONDS_PER_HOUR = 3600.0


@dataclass(frozen=True)
class Profitability:
    hashes_per_second: float
    block_probability_per_hash: float
    expected_blocks_per_hour: float
    expected_revenue_btc_per_hour: float
    expected_revenue_fiat_per_hour: float
    expected_cost_fiat_per_hour: float
    expected_profit_fiat_per_hour: float
    currency: str


def block_probability_per_hash(bits: int) -> float:
    """Probability a single hash meets the target = target / 2**256."""
    return bits_to_target(bits) / _HASH_SPACE


def expected_blocks_per_hour(hashes_per_second: float, bits: int) -> float:
    if hashes_per_second < 0:
        raise ValueError("hashes_per_second must be non-negative")
    return hashes_per_second * _SECONDS_PER_HOUR * block_probability_per_hash(bits)


def profitability(
    hashes_per_second: float,
    bits: int,
    height: int,
    total_fees: int,
    power_watts: float,
    electricity_cost_per_kwh: float,
    btc_price_fiat: float,
    currency: str = "USD",
) -> Profitability:
    """Full revenue/cost expectation for a live miner over one hour.

    Revenue is computed in BTC and converted to fiat with ``btc_price_fiat`` so
    that profit (revenue - cost) is expressed in a single, consistent unit.
    """
    if power_watts < 0:
        raise ValueError("power_watts must be non-negative")
    if electricity_cost_per_kwh < 0:
        raise ValueError("electricity_cost_per_kwh must be non-negative")
    if btc_price_fiat < 0:
        raise ValueError("btc_price_fiat must be non-negative")
    prob = block_probability_per_hash(bits)
    blocks_per_hour = hashes_per_second * _SECONDS_PER_HOUR * prob
    reward_btc = coinbase_value(height, total_fees) / COIN
    revenue_btc = blocks_per_hour * reward_btc
    revenue_fiat = revenue_btc * btc_price_fiat
    cost_fiat = (power_watts / 1000.0) * electricity_cost_per_kwh  # per hour
    return Profitability(
        hashes_per_second=hashes_per_second,
        block_probability_per_hash=prob,
        expected_blocks_per_hour=blocks_per_hour,
        expected_revenue_btc_per_hour=revenue_btc,
        expected_revenue_fiat_per_hour=revenue_fiat,
        expected_cost_fiat_per_hour=cost_fiat,
        expected_profit_fiat_per_hour=revenue_fiat - cost_fiat,
        currency=currency,
    )
