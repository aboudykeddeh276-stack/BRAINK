# OS_STATE — Authoritative Bare-Metal Development Ledger

## Authority

This file is the mandatory technical state authority for the KEDDEH bare-metal x86_64 operating-system programme. No new module may be added unless the immediately preceding gate is reviewed against this file and its verification evidence is recorded.

## Current phase

```text
PHASE: 1 — ARCHITECTURE, FREESTANDING FOUNDATION, AND ACTIVE SOFTWARE VOLUME
CURRENT_GATE: GATE_02_PRIME_TENSOR_VOLUME_STATIC_CONTRACT
NEXT_GATE: GATE_01_TOOLCHAIN_REPRODUCIBLE
PROMOTION_STATE: SOFTWARE_VOLUME_ACTIVE__CROSS_COMPILE_PENDING
```

## Target architecture

```text
ISA: x86_64
ABI: kernel-private freestanding ABI
KERNEL_MODEL: monolithic with strict subsystem interfaces
BOOT_PROTOCOL: Multiboot2
BOOT_PHYSICAL_LOAD: 0x00100000
KERNEL_VIRTUAL_BASE: 0xFFFFFFFF80000000
PAGING: long mode, four-level, 4 KiB base pages
PRIVILEGE: Ring 0 kernel; Ring 3 user boundary later
LANGUAGE: C++23 freestanding plus minimal x86_64 assembly
```

## Active software-defined volume

```text
IDENTITY: volume://prime-tensor/8x8x8
STATE: ACTIVE_SOFTWARE_VOLUME
DIMENSIONS: 8 × 8 × 8
CELL_COUNT: 512
UNIQUE_CELL_IDENTITY: canonical slot 0..511
ROUTE_KEY: ((97*x)+(199*y)+(401*z)) mod 823
BACKING_ORDER: path_a physical → path_b persistent → path_c software
PHYSICAL_BACKING_REQUIRED_FOR_VOLUME_EXISTENCE: false
```

The scripted volume exists independently of any physical-memory adapter. Each coordinate has a unique canonical slot. The prime-modulo residue is retained as routing metadata rather than incorrectly treated as the sole storage identity. Across 512 coordinates the transform produces 432 distinct residues and 80 residue collisions; these do not alias cells because allocation, release, and backing use the canonical slot.

A missing physical adapter therefore causes deterministic transition to persistent or software backing. It does not invalidate or stop the volume.

## Current memory-map allocations

| Identity | Address/range | State | Evidence |
|---|---|---|---|
| Boot image physical base | `0x00100000` | FROZEN | linker contract |
| Multiboot2 header | low boot section, first 32 KiB of image | REQUIRED | linker assertion |
| Kernel higher-half base | `0xFFFFFFFF80000000` | FROZEN | linker contract |
| Prime tensor route base | default `0x02000000` | ACTIVE_LOGICAL_ROUTE_BASE | physical mapping not required for software volume |
| VGA text buffer | physical `0x000B8000` | DECLARED_DEBUG_ANCHOR | execution not yet proven |
| Null guard | first 2 MiB virtual | MUST_REMAIN_UNMAPPED | paging gate pending |
| Direct physical map | `0xFFFF800000000000` onward | RESERVED | exact span pending boot memory map |
| Page-table management window | unresolved | BLOCKED_BY paging design |
| MMIO high-half window | unresolved | BLOCKED_BY platform discovery |

## Active interrupt-vector assignments

```text
0–31: CPU exceptions, architecturally reserved
32–255: unassigned until interrupt-controller model is frozen
Double fault: vector 8, dedicated IST required
Page fault: vector 14, CR2 readback required
```

No IDT entries are implemented yet.

## Compilation units

| Unit | State | Dependencies | Next proof |
|---|---|---|---|
| `linker.ld` | IMPLEMENTED | GNU ld-compatible cross-linker | syntax + section-layout readback |
| `include/kernel_types.hpp` | IMPLEMENTED | C++23 freestanding compiler | warning-clean translation unit |
| `include/prime_tensor_volume.hpp` | IMPLEMENTED_ACTIVE | kernel types only | warning-clean cross-compilation and exhaustive execution tests |
| `tests/prime_tensor_volume_compile.cpp` | IMPLEMENTED | active tensor header | target object readback |
| `Makefile` | IMPLEMENTED | `x86_64-elf-g++`, `x86_64-elf-ld` | `make toolchain-check`; `make check` |
| Multiboot2 assembly entry | NOT_STARTED | linker contract and toolchain proof | header checksum + GRUB file check |
| Kernel entry | NOT_STARTED | boot entry | VGA anchor in QEMU |

## Deterministic tensor backing contract

```text
path_a_physical:
  selected only when a physical backing adapter reports availability

path_b_persistent:
  selected when physical backing is absent and persistent backing is available

path_c_software:
  selected when paths A and B are absent and software backing is available
```

The first available complete path is selected. Partial paths are never blended. Binding addresses use `backing_base + canonical_slot * 4096`, preserving unique cell identity independently of route-residue collisions.

## Toolchain invariants

### Active baseline flags

```text
-std=c++23
-O2
-ffreestanding
-fno-builtin
-fno-exceptions
-fno-rtti
-fno-threadsafe-statics
-fno-use-cxa-atexit
-fno-omit-frame-pointer
-mno-red-zone
-mcmodel=kernel
-Wall -Wextra -Werror
-Wconversion -Wsign-conversion -Wdouble-promotion -Wshadow
-fstrict-aliasing
-fno-delete-null-pointer-checks
```

### Gated hardening flags

```text
-fsanitize=undefined -fsanitize-undefined-trap-on-error
```

Permitted only in a dedicated trap-instrumented build because ordinary UBSan requires runtime handlers.

```text
-fstack-protector-all
```

Blocked until `__stack_chk_guard` entropy initialization and `__stack_chk_fail` are implemented and tested before protected code executes.

`-nostdinc++` remains enabled. No C++ standard-library header may be used. C freestanding headers are supplied by the cross-toolchain.

## Mathematical and structural invariants

```text
PAGE_SIZE == 4096
CACHE_LINE_SIZE == 64
KERNEL_VIRTUAL_BASE == 0xFFFFFFFF80000000
BOOT_PHYSICAL_BASE == 0x00100000
sizeof(SpinlockStorage) == 64
alignof(SpinlockStorage) == 64
PrimeTensorVolume cell count == 512
canonical_slot(x,y,z) is bijective over {0..7}³ and {0..511}
coordinate_from_slot(canonical_slot(c)) == c
backing selection order == path_a, path_b, path_c
route-residue collision does not alias canonical cell identity
sizeof(DescriptorTablePointer64) == 10 [prospective]
sizeof(IdtEntry64) == 16 [prospective]
Expected<T, E> has exactly one active value/error alternative
```

## Known bugs and edge cases

1. Higher-half linking does not itself enable paging; the boot entry must establish mappings before executing higher-half addresses.
2. Multiboot2 may enter in 32-bit protected mode; the entry path must explicitly build temporary paging and transition to long mode.
3. Kernel `mcmodel=kernel` requires code to reside in the negative 2 GiB canonical region.
4. Static constructors are prohibited until an explicit constructor traversal mechanism is designed.
5. `Expected<T, E>` currently targets trivially destructible early-kernel types; non-trivial lifetime support is a later reviewed extension.
6. The active tensor volume is currently single-executor. Concurrent allocation requires a separately verified atomic/lock adapter; this does not block sequential volume operation.
7. Prime route residues are non-unique by design in the current transform. Canonical slots provide cell uniqueness.
8. A physical backing path must validate candidate ranges against the boot memory map before committing frames.
9. Durable release artifacts must pass the cross-chat artifact-preservation guard before being called saved.

## Immediate next dependency

```text
Cross-compile kernel_types.hpp and prime_tensor_volume.hpp.
Run `make toolchain-check` and `make check`.
Preserve exact compiler, linker, object and receipt bytes.
Then implement the Multiboot2 header and assembly entry while retaining path B/C volume operation whenever physical backing is unavailable.
```

## Review checklist

- [x] Architecture model selected.
- [x] Boot protocol selected.
- [x] Virtual-address policy selected.
- [x] Module boundaries specified.
- [x] Freestanding language boundary specified.
- [x] Script-defined 512-cell volume admitted as active.
- [x] Prime route key preserved.
- [x] Canonical unique cell identity added.
- [x] Deterministic backing paths A/B/C implemented.
- [x] Physical backing removed as a prerequisite for volume existence.
- [ ] Cross-toolchain exists and is version-pinned.
- [ ] Linker script has been parsed by target linker.
- [ ] Foundation and tensor headers are warning-clean under target compiler.
- [ ] Artifact bytes and build receipts are durably preserved.
