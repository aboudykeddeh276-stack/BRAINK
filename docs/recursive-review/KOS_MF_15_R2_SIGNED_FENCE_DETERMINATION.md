# KOS-MF-15 R2 Signed Native Fence Determination

Status: **PASS**.

R2 closes the R1 proof gap where the protected resource trusted a certificate voter list without independently authenticating each voter. The protected resource now verifies membership epoch/root, owner proposal signature, proposal root, each Ed25519 vote signature, unique quorum membership, vote/proposal slot consistency, certificate root, generation continuity and stale-generation rejection.

Hostile suite: 6/6 PASS with `ResourceWarning` promoted to execution error.

Classification: `SIGNED_FIXED_MEMBERSHIP_CRASH_FAULT_FENCE_MODEL_VALIDATED`.

Promotion boundary: physical distinct-host execution, WAN partition/reordering campaigns, leader/view-change liveness, dynamic membership, Byzantine safety and hardware-rooted keys remain separate gates.
