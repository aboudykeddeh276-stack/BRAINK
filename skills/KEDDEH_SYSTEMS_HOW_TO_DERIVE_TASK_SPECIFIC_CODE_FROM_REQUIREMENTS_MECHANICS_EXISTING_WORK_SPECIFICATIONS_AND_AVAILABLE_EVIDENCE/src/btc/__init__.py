"""Canonical BTC mining mechanics — one authoritative implementation each.

This package embodies the working principle:

    One mechanic, one authoritative implementation, many consumers.
    Tests verify mechanics; they do not recreate them.
    Packaging relocates mechanics; it does not redefine them.
    Repository organisation describes mechanics; it does not become another
    execution architecture.

Each module implements exactly one mechanic of the BTC assembly/execution chain:

    template -> coinbase -> witness commitment -> merkle root -> header
             -> work -> hash -> candidate -> full block -> submit

`pipeline.py` composes these same functions; tests, runtime, CLI, and any package
all consume the identical implementations rather than rewriting them.
"""
