# KEDDEH Bare-Metal OS Architecture Baseline

## System target

- Architecture: x86_64
- Kernel model: monolithic kernel with explicit internal subsystem boundaries
- Boot protocol: Multiboot2 first implementation; UEFI remains a later adapter, not an initial dependency
- Language boundary: freestanding Rust `#![no_std]` for kernel logic, minimal x86_64 assembly for entry and privileged transitions
- Hosted dependency policy: no libc, no host OS services, no Linux syscalls, no standard library assumptions inside the kernel
- Initial output: VGA text buffer at physical address `0xB8000`, then serial, then framebuffer

## Architectural block diagram

```text
BOOT IMAGE
  └─ Multiboot2 header
       └─ x86_64 assembly entry
            ├─ establish known stack
            ├─ validate boot magic and information pointer
            ├─ enable required CPU state
            └─ call Rust kernel entry

KERNEL ENTRY
  ├─ early console / VGA anchor
  ├─ boot-information parser
  ├─ memory-map authority
  ├─ architecture layer
  │    ├─ GDT
  │    ├─ TSS
  │    ├─ IDT
  │    ├─ ISR/exception handlers
  │    ├─ control registers
  │    └─ port/MMIO primitives
  ├─ physical memory manager
  ├─ virtual memory manager
  ├─ kernel heap
  ├─ scheduler and task model
  ├─ user-space boundary
  ├─ syscall boundary
  ├─ device-driver boundary
  ├─ VFS and storage
  └─ process and service runtime
```

## Canonical memory map

The bootloader-provided memory map is authoritative for physical availability. The kernel never assumes that unspecified physical memory is free.

### Initial virtual layout

| Region | Virtual range | Purpose |
|---|---|---|
| Null guard | `0x0000000000000000`–`0x00000000001FFFFF` | intentionally unmapped low-address guard |
| User lower canonical half | `0x0000000000200000`–`0x00007FFFFFFFFFFF` | later Ring 3 address spaces |
| Direct physical map | `0xFFFF800000000000` onward | controlled physical-memory window |
| Kernel image | `0xFFFFFFFF80000000` onward | higher-half kernel text, rodata, data, bss |
| Recursive or page-table management window | fixed by paging design before implementation | page-table inspection and edits |
| MMIO window | reserved high-half subrange | explicitly mapped device memory |
| Kernel stacks | guarded high-half allocations | per-CPU and per-task stacks |

Exact linker addresses and page-table slot assignments must be frozen before paging code is admitted.

## Module boundaries

```text
kernel/
  arch/x86_64/
    boot/
    cpu/
    gdt/
    tss/
    idt/
    interrupts/
    paging/
    io/
  memory/
    physical/
    virtual/
    heap/
  task/
    scheduler/
    pcb/
    context_switch/
  user/
    address_space/
    syscall/
    privilege/
  drivers/
    console/
    serial/
    timer/
    interrupt_controller/
    storage/
  fs/
    vfs/
  diagnostics/
  synchronization/
```

No module may reach across another module's private state. Cross-module interaction requires a typed public interface.

## Design invariants

1. The kernel is freestanding and `no_std`.
2. The kernel must boot without libc, POSIX, Linux, or host-process abstractions.
3. Every physical allocation originates from the parsed boot memory map.
4. Kernel image, boot information, page tables, framebuffer, ACPI structures, and reserved regions are never allocatable.
5. Interrupts remain disabled until GDT, TSS, IDT, exception handlers, and known stacks are installed.
6. Double fault uses a dedicated IST stack before interrupts are enabled.
7. Every CPU exception has an explicit handler and diagnostic record.
8. Page-fault reporting includes fault address, error code, instruction pointer, stack pointer, and privilege state.
9. Writable kernel pages are non-executable wherever hardware permits.
10. Executable kernel pages are read-only wherever hardware permits.
11. CR0 write protection remains enabled after paging initialization.
12. User pages never map kernel-writable memory.
13. Drivers interact through explicit port-I/O or MMIO abstractions; no driver mutates scheduler or memory-manager internals.
14. Process identity, address space, kernel stack, user stack, register state, scheduling state, and ownership are explicit PCB fields.
15. A module is not advanced until it compiles, passes static checks, has negative tests or deterministic emulator checks, and updates `OS_STATE.md`.
16. Artifact outputs are not considered saved until durable-byte readback, stable identity, size, and SHA-256 are recorded by the artifact-preservation guard.
17. Missing optional hardware removes only the capability supplied by that hardware; deterministic failover paths remain output-specific.
18. No test, UI string, emulator animation, or manifest alone proves hardware execution.

## Development gates

```text
GATE_00_ARCHITECTURE_FROZEN
GATE_01_TOOLCHAIN_REPRODUCIBLE
GATE_02_MULTIBOOT2_HEADER_VALID
GATE_03_KERNEL_ENTRY_REACHED
GATE_04_VGA_ANCHOR_READBACK
GATE_05_GDT_TSS_LOADED
GATE_06_IDT_EXCEPTION_MATRIX
GATE_07_BOOT_MEMORY_MAP_PROTECTED
GATE_08_PHYSICAL_ALLOCATOR
GATE_09_PAGING_PROTECTIONS
GATE_10_KERNEL_HEAP
GATE_11_TIMER_AND_PREEMPTION
GATE_12_RING3_TRANSITION
GATE_13_SYSCALL_BOUNDARY
GATE_14_DRIVER_ISOLATION
GATE_15_VFS_AND_PROCESS_RUNTIME
```

No later gate may be used as evidence for an earlier gate.
