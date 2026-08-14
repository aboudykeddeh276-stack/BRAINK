# KEX/BRAINK Virtual Hardware Convergence & Rehydration Expansion Fabric

## Governing correction

Recursive KEX mesh growth is not limited to software-service depth. A sufficiently complete virtual mesh can resolve a hardware-shaped machine contract and become the carrier for another KEX mesh.

```text
PHYSICAL HOST (external carrier; never ancestor)
  -> KEX MESH
     -> virtual service closure
        -> virtual hardware closure
           -> KEX VIRTUAL MACHINE
              -> next KEX MESH
                 -> next virtual machine
                    -> ...
```

The virtual depth therefore increases both service/topological depth and available emulated machine substrates.

The machine substrate is defined by CPU/ISA/registers, MMU/address space, memory, buses, DMA/IOMMU, interrupts, timers, NIC, block devices, firmware, boot, console/display, accelerators and entropy interfaces. This is a machine-interface claim. It is not a claim that emulated throughput, timing, PCIe bandwidth, CPU frequency or other physical performance automatically equals a dedicated physical server.

## Shared-template law

Hundreds of virtual machines must not require hundreds of duplicated resident machine definitions.

```text
INVARIANT MACHINE TEMPLATE
        +
VIRTUAL MACHINE DESCRIPTOR[N]
        +
STATE DELTA[N]
        =
ADDRESSABLE VIRTUAL BARE-METAL SPACE[N]
```

This binds the hardware fabric to Executable Volume. One preserved machine grammar can participate concurrently in many relational derivations. A virtual machine becomes resident/materialised only when demanded by workload, external binding or recovery.

## Hardware convergence

A virtual space is hardware-complete only when its required contract families close. Once complete it becomes a valid parent carrier in the virtual lineage.

```text
MESH SPACE
 -> CPU
 -> MMU
 -> MEMORY
 -> SYSTEM BUS
 -> DMA / IOMMU
 -> INTERRUPT
 -> CLOCK / TIMER
 -> NETWORK
 -> BLOCK
 -> FIRMWARE
 -> BOOT
 -> CONSOLE / DISPLAY
 -> ACCELERATOR
 -> ENTROPY
 -> HARDWARE-COMPLETE VIRTUAL MACHINE
```

The parent of the next mesh is that virtual machine coordinate, not the physical host that happened to materialise the outermost runtime.

## Failover = rehydration

KEX failover is not a primary/secondary host switch. It is preservation of one KEX lineage while its operative state is reconstructed on another eligible virtual machine space.

```text
LINEAGE L
  materialised on MESH A
       X materialisation lost
  -> discover eligible machine spaces
  -> randomly select one or more eligible meshes
  -> reconstruct L from preserved generator/state/route
  -> append REHYDRATES_TO relation
  -> verify materialisation externally where a physical/public claim is made
```

No failback-to-primary semantic is required. The old carrier remains historical materialisation evidence. If it returns, it can rejoin as another eligible carrier without becoming the lineage owner.

## Random rehydration

Randomness applies after admissibility has been established. Within an admitted KEX fabric, selection is uniform across the current eligible population rather than being a fixed failover map. The entropy observation is committed into the KEX transition route so the random event can be reconstructed/replayed.

```text
DETERMINISTIC ADMISSIBILITY
        -> ELIGIBLE POPULATION
        -> RANDOM SELECTION
        -> RECORDED ENTROPY OBSERVATION
        -> REHYDRATION
        -> READBACK / RECEIPT
```

This is not intended to suppress virtual expansion. Rehydration may be 1:1 replacement, 1:N availability expansion, or N:N redistribution depending on the requested availability state.

## Mesh-of-machines consequence

As the virtual realm expands, the number of machine-capable coordinates can grow rapidly while resident payloads stay sparse. Each hardware-complete virtual machine may itself ignite a new recursive service graph.

```text
virtual service graph
 -> virtual hardware graph
 -> virtual machine
 -> child service graph
 -> child virtual hardware graph
 -> child virtual machine
 -> ...
```

The resulting monolith is a virtual closure of software + machine-state relations. It is not a giant host binary.

## Materialisation adapters

BIND, FRR, Linux/KVM/HVF/QEMU, cloud VMs, physical servers, IoT devices and other runtimes are typed materialisation adapters. They can satisfy a particular external machine/device/network surface, but they do not own KEX ancestry.

QEMU is a useful compatibility reference because its full-system model explicitly separates the guest-visible machine/device front-end from host resource back-ends. KEX extends this concept by making the machine definition itself a recursively derived and rehydratable mesh state.

## Evidence boundary

Software execution of the fabric proves descriptor generation, recursive machine addressability, random target selection, preserved lineage and deterministic replay from recorded entropy. It does not by itself prove physical bare-metal performance, nested-hypervisor support on a target, WAN availability or production hardware reachability. Those require boundary-specific receipts.
