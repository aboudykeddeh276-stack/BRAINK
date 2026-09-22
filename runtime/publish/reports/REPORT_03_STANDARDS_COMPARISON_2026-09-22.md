# REPORT 03 — Current Standards Comparison, Layer 1–9 Qualification

Date: 2026-09-22

This report compares the executed BRAINK/KEX Report 03 R2 implementation with current published/reference standards and established system architectures. It does not claim conformance merely because similar words appear in both systems.

## 1. Raft consensus

Reference: https://raft.github.io/

Raft remains the relevant crash-fault replicated-state-machine comparison. Its reference material separates leader election, log replication, safety, and membership changes; the extended paper describes majority progress and overlapping-majority membership transition, and the project publishes a TLA+ specification.

BRAINK R2 now has:
- fixed-membership majority commits in ToT;
- per-voter equivocation lock;
- quorum certificate/receipt hashes;
- deterministic committed-root chain;
- Layer 6 binding to membership, certificate and receipt hashes.

BRAINK R2 does not have:
- independent peer transport;
- leader election or equivalent distributed serialization authority;
- AppendEntries-style replicated log repair;
- persistent term/vote state;
- safe membership transition.

Result: ToT is a fixed-membership non-Byzantine safety kernel, not a Raft-equivalent consensus service.

## 2. etcd distributed coordination

References:
- https://etcd.io/docs/
- https://etcd.io/docs/v3.6/learning/api/
- https://etcd.io/docs/v3.6/tuning/
- https://etcd.io/docs/v3.6/learning/design-learner/

etcd exposes revisions, Raft terms, linearizable/default reads, serializable local reads, watches, membership services, snapshots and persistent storage behavior. Its learner design explicitly treats membership changes as operationally dangerous.

BRAINK R2 now has deterministic committed coordinate state, generation fencing, directory roots, replica replay/divergence detection, snapshot-root validation in the existing Report 03 baseline, and a Layer 3 binding that consumes the committed directory root.

Still absent are network-accessible linearizable reads/writes, revisioned client transactions, leases, watches, compaction, consensus-backed concurrent clients and replicated storage across independent machines.

Result: the directory is a verified deterministic coordinate state machine, not an etcd-class coordination service.

## 3. Kubernetes controller model

Reference: https://kubernetes.io/docs/concepts/architecture/controller/

Kubernetes controllers repeatedly compare desired and current state and act to move current state toward desired state.

BRAINK R2's existing Layer-2 reconciler follows that shape materially:
- desired and observed state are distinct;
- actions have deterministic idempotency keys;
- actuator readback is validated;
- partial failure is explicit;
- retry can converge.

R2 adds a stricter boundary: Layer 7 execution does not imply Layer 8 observation or Layer 9 evidence. A failed Layer 7 leaves only Layers 1–6 committed.

Missing controller-platform architecture includes durable shared work queues, ownership/finalizer semantics, resource versions, distributed controller leases, per-target rate/backoff policy and production adapter matrices.

## 4. IETF NMDA — RFC 8342

Reference: https://www.rfc-editor.org/info/rfc8342/

RFC 8342 distinguishes intended configuration from operational state. R2 follows that distinction at Layer 7/8: an execution result and an independently observed state are separate artifacts.

R2 does not implement NETCONF/YANG datastores, running/intended/operational datastore semantics, origin metadata or schema validation.

## 5. IETF topology — RFC 8345

Reference: https://www.rfc-editor.org/info/rfc8345/

RFC 8345 models networks, nodes, links and termination points and allows dependencies across layered topologies.

The BRAINK coordinate directory and Layer 5 propagation records can be projected into similar graph concepts, but no YANG/RFC 8345 mapping or interoperability suite exists. The custom nine-layer pipeline must not be described as RFC 8345 compliant.

## 6. JSON Canonicalization Scheme — RFC 8785

Reference: https://www.rfc-editor.org/rfc/rfc8785.html

R2 hashes deterministic Python JSON generated with sorted keys and compact separators. That is deterministic within this implementation profile. RFC 8785 additionally constrains JSON values and serialization rules to achieve interoperable canonical JSON.

Result: R2 hashes are implementation-profile deterministic; JCS conformance remains unproven until an RFC 8785 implementation and cross-language test corpus are used.

## 7. NIST SP 800-207 / 800-207A

References:
- https://csrc.nist.gov/pubs/sp/800/207/final
- https://csrc.nist.gov/pubs/sp/800/207/a/final

NIST's zero-trust model rejects implicit trust based merely on network location or ownership and emphasizes explicit subject/service identity and authorization.

R2's Layer 2 requires actor identity, authority reference and capability. That is an improvement over coordinate/location trust. It is not a complete ZTA: there is no service identity issuance, attestation, dynamic policy engine, token lifecycle, revocation or distributed policy enforcement plane.

## 8. SLSA 1.2 and in-toto stable specifications

References:
- https://slsa.dev/spec/v1.2/
- https://slsa.dev/spec/v1.2/provenance
- https://in-toto.io/docs/specs/

SLSA 1.2 treats provenance as verifiable information describing where, when and how artifacts were produced. in-toto stable v1.0 defines software-supply-chain attestation specifications.

R2 produces hash-bound local execution and fault receipts. Those receipts are not SLSA provenance and are not signed in-toto attestations. Missing architecture includes builder identity, trusted signer/verifier separation, standard statement envelopes, key lifecycle and independent verification.

## 9. IEEE 802.1Q-2022

Reference: https://standards.ieee.org/ieee/802.1Q/10323/

IEEE lists 802.1Q-2022 as an active standard for bridges and bridged networks, including MAC/VLAN bridge operation, management, protocols and algorithms.

BRAINK's Layer 2 and Layer 5 are reconciliation/propagation control stages. They do not implement MAC learning, forwarding databases, VLAN tagging, spanning-tree behavior, Ethernet ingress/egress or line-rate bridge dataplane operation.

Result: no IEEE 802.1Q conformance claim is supported by R2.

## 10. Standards conclusion

R2 is closest to a composition of:
- fixed-membership crash-fault safety primitives;
- deterministic coordinate-state machinery;
- controller-style reconciliation;
- explicit execution/readback/evidence stages.

Its missing architectures are the same ones established systems separate explicitly: distributed consensus transport/election/log replication, durable replicated storage, standardized management models, identity lifecycle, production controller infrastructure, interoperable canonicalization and authenticated provenance.
