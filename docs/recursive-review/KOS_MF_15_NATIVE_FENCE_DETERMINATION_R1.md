# KOS-MF-15 Native Mesh Fencing Determination R1

Status: **PASS in the fixed-membership crash-fault model**.

This extension composes the existing KEX Mesh quorum substrate into a fencing authority model instead of introducing etcd/Consul/Redis/ZooKeeper as mandatory dependencies.

Implemented and executed:
- membership epoch + membership-root binding;
- durable one-vote-per-resource/generation;
- quorum-certified monotonic fence generations;
- resource-side stale-fence rejection;
- persistent replay high-water counters;
- minority-partition refusal;
- stale-owner rejection before and after partition heal;
- conflicting same-generation proposal rejection;
- vote-conflict persistence across node restart.

Local hostile suite: 6/6 PASS.

Classification: `FIXED_MEMBERSHIP_CRASH_FAULT_FENCE_MODEL_VALIDATED`.

Claim boundary: this is a deterministic protocol/model validation using independent durable node stores. It does not yet prove physical multi-host operation, WAN partition behavior, leader/view-change liveness, dynamic membership, Byzantine safety, or hardware-rooted identity.

Next physical gate: launch the existing KEX Mesh private-host configuration on distinct hosts and run the same fencing contract through the actual signed proposal/vote/commit transport. The resource being mutated must retain the maximum accepted fence generation and reject any lower or duplicate generation regardless of the claimant's local lease belief.
