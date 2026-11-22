# R87 — P11 carrier identity collision correction candidate

**Architect/source authority:** A. Keddeh  
**Canonical architecture:** KS-BRAINK-IL-LLM  
**Disposition:** additive proposal; not promoted  

The R86 read-only traversal found three legacy carrier IDs, each resolving to two distinct JSON payloads. Each pair retains one `READY_NEXT` and one `COMPLETED` lifecycle snapshot. They share one logical identity per pair but cannot safely share one content locator.

No original P11 row, source file, workbook, alias, or logical identity is changed. The proposal adds content-addressed variant locators using the full SHA-256. The original carrier ID remains an ambiguous legacy alias and must fail closed unless a variant digest is supplied.

| Legacy carrier ID | Logical identity | Source rows | Lifecycle variants |
|---|---|---:|---|
| `carrier://json/p03-action-plan` | `artifact://p03-action-plan` | 59, 60 | `READY_NEXT`, `COMPLETED` |
| `carrier://json/p04-action-plan` | `artifact://p04-action-plan` | 63, 64 | `READY_NEXT`, `COMPLETED` |
| `carrier://json/p05-action-plan` | `artifact://p05-action-plan` | 67, 68 | `READY_NEXT`, `COMPLETED` |

## Source identity

- R4 bytes: 21,492,468
- R4 SHA-256: `e797bc65e71150c300d838616aa39dea7258f53bcd0b77d6c1aa1aad2cc160d9`
- P11 raw registry rows: 98
- Unique legacy carrier IDs: 95
- Logical objects: 76
- Exact source variants re-extracted and verified locally: 6

## Variant locators

- `carrier://json/p03-action-plan/sha256/6cc90b04de0fa57655a3ed98346e03a68f8739055a85a145af6da7933ebf821e` — READY_NEXT, row 59, 1803 bytes, SHA-256 `6cc90b04de0fa57655a3ed98346e03a68f8739055a85a145af6da7933ebf821e`
- `carrier://json/p03-action-plan/sha256/011947a2d38262751cd65d41bef5a731570aa8a5793c8e7c35622f3b52cf6b98` — COMPLETED, row 60, 1546 bytes, SHA-256 `011947a2d38262751cd65d41bef5a731570aa8a5793c8e7c35622f3b52cf6b98`
- `carrier://json/p04-action-plan/sha256/fbed1d92b6839db0442c88281917d387c7455168b9ab630204a8fdf05105c319` — READY_NEXT, row 63, 1559 bytes, SHA-256 `fbed1d92b6839db0442c88281917d387c7455168b9ab630204a8fdf05105c319`
- `carrier://json/p04-action-plan/sha256/6da9fdf660d6d0f02b149a4c2138c7b8ecb3bd178fedc919f0ea0f2a1f9e1c8c` — COMPLETED, row 64, 1576 bytes, SHA-256 `6da9fdf660d6d0f02b149a4c2138c7b8ecb3bd178fedc919f0ea0f2a1f9e1c8c`
- `carrier://json/p05-action-plan/sha256/bae9bffe078871099eda0c54dd4df46d7f4f1ddec2af4cf17a89195be11809f8` — READY_NEXT, row 67, 1723 bytes, SHA-256 `bae9bffe078871099eda0c54dd4df46d7f4f1ddec2af4cf17a89195be11809f8`
- `carrier://json/p05-action-plan/sha256/cd3c5613975165144c593f46a1f82a74d1f0ff063e571aed36b2ec8f343f0aa2` — COMPLETED, row 68, 1754 bytes, SHA-256 `cd3c5613975165144c593f46a1f82a74d1f0ff063e571aed36b2ec8f343f0aa2`

## Qualification boundary

The variant IDs are content-addressed transport identities. They do not create new logical objects, prove the underlying action plan was executed, or authorize promotion. The two lifecycle snapshots remain distinct source payloads under the same logical identity.

The local source verifier re-extracts the six exact script innerText payloads from the source identified above and checks their UTF-8 byte lengths, SHA-256 values, plan labels and lifecycle statuses. CI tests validate the additive manifest invariants; they do not substitute fixtures for the full source. The original 21.49 MB R4 HTML and original registry workbook are not rewritten or replaced.