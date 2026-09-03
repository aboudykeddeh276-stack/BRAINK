# Cross-Platform Contract

## Principle

The actuator asset is portable by capability, not by hard-coded operating-system identity.

## Required host capabilities

- Python 3 with `sqlite3`, `ssl`, `socket`, `hashlib`, `json`, `pathlib`;
- atomic replace semantics or a platform adapter that provides equivalent replacement guarantees;
- durable file flush capability or explicit weaker durability classification;
- executable process restart interface;
- TLS client capability for live certificate readback;
- ACME-capable client or provider adapter;
- access to the resident registrar state through an approved interface;
- ability to resolve the live server certificate/key binding.

## Linux/Unix adapter

Current implementation uses POSIX-style filesystem/process conventions and is the primary qualified target.

## macOS adapter

Python/OpenSSL/filesystem semantics are broadly compatible, but service restart paths, certificate-loader paths and self-hosted-runner filesystem roots must be adapted explicitly. Do not assume `/mnt/data` or Linux service layout.

## Windows adapter

Windows requires explicit adapters for file locking/replacement, executable/script launch conventions, process/service restart and path discovery. The semantic interfaces remain DNS challenge publish/cleanup, certificate install/rollback and live TLS readback.

## Container/VM adapter

The same contract applies when the registrar/server lives in a container or VM. Bindings must identify the namespace where the state and TLS loader actually exist. Host paths outside that namespace are not proof of guest consumption.

## Remote/serverless/cloud adaptation

Provider APIs may implement the same interfaces if they have actual mutation authority. Provider-specific adapters must preserve:

- typed object identity;
- authority classification;
- pre/post readback;
- rollback semantics where available;
- evidence schema;
- dependency graph representation.

## Cross-platform invariant

Changing the carrier, OS, package manager, filesystem path or service manager must not change the semantic identity of `TLS_ROOT`, `DNS_ROOT`, `DOMAIN_ROOT` or `SERVER_ROOT`.
