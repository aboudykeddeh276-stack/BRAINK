# OS_STATE — Authoritative Bare-Metal Development Ledger

## Authority

This file is the mandatory technical state authority for the KEDDEH bare-metal x86_64 operating-system programme. No new module may be added unless the immediately preceding gate is reviewed against this file and its verification evidence is recorded.

## Current phase

```text
PHASE: 1 — ARCHITECTURE AND FREESTANDING FOUNDATION
CURRENT_GATE: GATE_00_ARCHITECTURE_FROZEN
NEXT_GATE: GATE_01_TOOLCHAIN_REPRODUCIBLE
PROMOTION_STATE: IMPLEMENTED_NOT_YET_CROSS_COMPILED
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

## Current memory-map allocations

| Identity | Address/range | State | Evidence |
|---|---|---|---|
| Boot image physical base | `0x00100000` | FROZEN | linker contract |
| Multiboot2 header | low boot section, first 32 KiB of image | REQUIRED | linker assertion |
| Kernel higher-half base | `0xFFFFFFFF80000000` | FROZEN | linker contract |
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
| `Makefile` | IMPLEMENTED | `x86_64-elf-g++`, `x86_64-elf-ld` | `make toolchain-check`; `make check` |
| Multiboot2 assembly entry | NOT_STARTED | linker contract and toolchain proof | header checksum + GRUB file check |
| Kernel entry | NOT_STARTED | boot entry | VGA anchor in QEMU |

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
sizeof(DescriptorTablePointer64) == 10
sizeof(IdtEntry64) == 16
all packed hardware structures have exact static_assert geometry
all cache-sensitive synchronization storage is alignas(64)
Expected<T, E> has exactly one active value/error alternative
```

The descriptor types are not yet implemented; their size invariants are prospective gates, not current proof claims.

## Known bugs and edge cases

1. Higher-half linking does not itself enable paging; the boot entry must establish mappings before executing higher-half addresses.
2. Multiboot2 may enter in 32-bit protected mode; the entry path must explicitly build temporary paging and transition to long mode.
3. Kernel `mcmodel=kernel` requires code to reside in the negative 2 GiB canonical region.
4. Static constructors are prohibited until an explicit constructor traversal mechanism is designed.
5. `Expected<T, E>` currently targets trivially destructible early-kernel types; non-trivial lifetime support is a later reviewed extension.
6. Packed structures must not be dereferenced through potentially unaligned native references.
7. Compiler-provided atomic builtins may introduce external runtime calls for unsupported widths; only verified lock-free widths may be admitted.
8. Durable release artifacts must pass the cross-chat artifact-preservation guard before being called saved.

## Immediate next dependency

```text
Install or provision an x86_64-elf GCC/binutils cross-toolchain.
Run `make toolchain-check`.
Run `make check` to compile the freestanding header translation unit and parse the linker script.
Record exact compiler, linker, and assembler versions.
Only then implement the Multiboot2 header and assembly entry.
```

## Review checklist

- [x] Architecture model selected.
- [x] Boot protocol selected.
- [x] Virtual-address policy selected.
- [x] Module boundaries specified.
- [x] Freestanding language boundary specified.
- [x] Inconsistent sanitizer/stack-protector assumptions isolated behind gates.
- [ ] Cross-toolchain exists and is version-pinned.
- [ ] Linker script has been parsed by target linker.
- [ ] Foundation header is warning-clean under target compiler.
- [ ] Artifact bytes and build receipts are durably preserved.
