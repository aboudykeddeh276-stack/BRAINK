# CarrierScale Slice-1 — arbitrary-byte transport dependency

Status: **development candidate / source implemented / runtime guest integration unproven**.

This directory supplies the dependency that can be integrated once the actual Linux guest boundary is identified. It intentionally does **not** claim that the V73 branch already transports bytes into a guest.

## Contract

`host bytes -> bounded frames -> guest adapter -> validated reassembly -> acknowledgement receipt`

The transport layer treats payloads as opaque bytes. Transport does not imply execution.

## Source-level guarantees

- accepts every byte value including NUL;
- bounded maximum payload and frame size;
- transfer identity binding;
- frame ordering/index validation;
- SHA-256 integrity per frame;
- duplicate, missing, corrupt and truncated frame rejection;
- deterministic reassembly;
- source/model-local round-trip receipt.

## Explicitly not proven yet

- Linux guest boot;
- actual host-to-guest delivery;
- guest-side adapter availability;
- virtio/serial/9p/vsock channel selection;
- runtime acknowledgement from a guest;
- restart/cancellation behavior at the real guest boundary;
- throughput or hardware performance.

## Integration gate

Do not promote this candidate beyond SOURCE_VERIFIED until a concrete guest adapter is located or implemented and an executable receipt proves:

1. Linux guest boot receipt exists.
2. Host payload is framed by this contract.
3. Frames cross the real host/guest boundary.
4. Guest reassembles the bytes without interpreting them.
5. `SHA256(host_payload) == SHA256(guest_payload)`.
6. Receipt identifies the realized transport authority and timestamps.
7. Boot/restart/security regression tests pass.

The intended invariant is:

`Transport(bytes) != Execute(bytes)`.
