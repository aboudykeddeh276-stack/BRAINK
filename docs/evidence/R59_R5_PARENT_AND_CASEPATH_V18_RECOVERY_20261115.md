# R59 — R5 parent and CasePath v18 recovery

**Architect/source authority:** A. Keddeh  
**Canonical architecture:** KS-BRAINK-IL-LLM  
**Disposition:** exact-byte source recovery and local verification only. No merge, promotion, deployment or host admission.

## Exact source matches

| Identity | Bytes | SHA-256 |
|---|---:|---|
| `braink://volume/r5/system-orchestrator` | 13,086,990 | `9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede` |
| `braink://volume/r4` | 13,050,075 | `5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592` |
| `app://casepath/analytical-matter-mesh/v18` | 252,033 | `d57cfd37e45e05357a061cc9b3d8e0c9fdb57e6921a06a8627bdc2c2682978e7` |

R5 and R4 source hashes match the R5 test receipt's artifact/parent hashes and the cross-work manifest's parent bindings. The standalone R5 manifest is 32,546 bytes, SHA-256 `a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc`. The cross-work manifest remains a distinct descendant identity, `braink://volume/r5/system-orchestrator/cross-work-r1`, SHA-256 `5d867ae7d7f517d6cdde14c138e67e90571062521e5d912fd8812165da1ce985`.

CasePath v18 is an `ADJACENT_SPECIALISATION` of `app://casepath`, not a parent or replacement for its separate v19 public projection, executable volume or `os://casepath/v2` appliance.

## Fresh local verification

Command: `python3 -m unittest -v test_r59_parent_recovery`

- 28 passed, 0 failed; exit 0; 2.161 seconds
- Python 3.13.5; Node v22.16.0
- PID 1406; one-shot process, no heartbeat
- Test source SHA-256: `ae765e2fd152734bbe921086fee4ffa3792483d0205c6170f607425c6adf1214`
- Stdout SHA-256: `acfb96de4b08d3d8f3e53d59981dc29fdced54b58e57d4e698d999b5aeecd4fa`

The existing R5 receipt marks 24/24 historical checks PASS; that historical harness was not rerun. Fresh checks parsed 48 R5 and 46 R4 embedded JSON blocks, verified unique DOM IDs, and passed Node syntax checks for 27 R5 and 26 R4 inline JavaScript blocks.

Both volumes reference one external v86 loader, `https://copy.sh/v86/build/libv86.js`. The R5 receipt still records browser navigation blocked by `net::ERR_BLOCKED_BY_ADMINISTRATOR`. No v86 boot, Chromium 100-pass polygon or persistent browser execution is claimed.

## Retained gaps

- `candidate://app/kos-bos/json-manifest-fixed` remains `CANDIDATE_UNPROMOTED`; candidate hash `05a8ff7abb6f9300c080ef943c1d24435dd0df7e6703ac8a648da0358d70fbaf`. Only the 495-byte KOS manifest metadata was found in the accessible Library; original HTML and candidate bytes were not materialized.
- Exact v6.0 base archive remains unlocated; required SHA-256 `12cc18e7d8d438926614613c704e7a0122b21c3a52935acb795b738d412dfbfd`. v6.1 remains preserved and unapplied.
- No direct Google Drive connector was exposed; this is a Files Library read, not a live Drive read/upload.
- PR #107 remains OPEN / DRAFT / UNMERGED at `db90d939bdb83c9f279a4586dd141610ff7e1664`; current-head full suite remains unexecuted. Runs 40514839575, 40519235354 and 43313091769 have zero steps and log downloads return 404 `BlobNotFound`; provider-side cause UNKNOWN.
- KEDDEH broker remains `BROKER_ONLY`, 0 registered/online external nodes. No pairing, BOOT_SUBSTRATE, host PID, heartbeat or restart receipt was created.
- Existing workflow `KEX-WF-8F124FF0B9F70FDBD66A` remains ACTIVE and dispatch `KEX-DISPATCH-211F545D697D25454F55` remains QUEUED. Neither was replayed.
