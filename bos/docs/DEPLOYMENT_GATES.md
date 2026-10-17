# BOS Recovery Deployment Gates

| Gate | Required receipt | Current status |
|---|---|---|
| E2-RUST | Format, unit tests, Clippy, `no_std` target check | CI workflow supplied; pending run |
| E3-LINUX-RING | Restricted ring construction and exact fixed-buffer file-image read | Code supplied; target runtime test pending |
| E3-FAULT | Torn-write and flush-boundary replay with `dm-flakey` / `dm-log-writes` | Open |
| E4-TPM | Quote, nonce, event-log replay, policy-bound vote key, monotonic anchor | Open |
| E4-IOMMU | Device-to-domain attachment and DMA escape rejection | Open |
| E4-NVME | Native queue, MSI-X, timeout, abort, reset, and FUA/flush receipts | Open |
| E4-MESH | Authenticated routes, membership epoch, durable no-double-vote ledger | Open |
| E5-POWER | Repeated physical power-cut tests across every root commit boundary | Open |
| E5-PARTITION | Multi-node partition/rejoin without conflicting commit certificates | Open |

No physical production volume should be attached writable before every E4/E5
receipt relevant to that target has passed.
