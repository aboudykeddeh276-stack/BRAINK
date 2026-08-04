# Prime Tensor Volume — Identity, Projection, and Backing Architecture

## Canonical law

The tensor volume is created by its script-defined coordinate domain, allocation topology, occupancy state, address transformation, and release/re-entry semantics. A physical mapping is one consumer of that volume; it is not the condition that creates the volume.

```text
VOLUME_IDENTITY != BACKING_IDENTITY
UNAVAILABLE_PHYSICAL_ADAPTER != UNAVAILABLE_TENSOR_VOLUME
```

## Volume definition

```text
V = {(x,y,z) | 0 <= x,y,z < 8}
|V| = 8^3 = 512
```

Each coordinate has a unique canonical slot:

```text
S(x,y,z) = 64*x + 8*y + z
S : V -> {0..511}
```

The prime-modulo transform is retained as a deterministic route key:

```text
R(x,y,z) = ((97*x) + (199*y) + (401*z)) mod 823
A_route(x,y,z) = B_route + R(x,y,z) * 1667 * 4096
```

The route key does not replace canonical identity. Coordinate, canonical slot, occupancy state, route residue, allocation lineage, and receipts remain invariant across every backing projection.

## Strict failover paths

The backing resolver evaluates exactly three ordered paths. Paths are not blended.

### path_a — physical projection

Ordered adapter kinds:

1. `physical_frame`
2. `device_mmio`

These adapters project a tensor cell into physical RAM, device memory, or an MMIO region. They may require boot-memory-map, page-table, permission, or device validation before the projection is committed. Their absence does not affect volume existence.

### path_b — persistent or externally projected storage

Ordered adapter kinds:

1. `persistent_volume`
2. `file_backed_storage`
3. `workbook_cells`
4. `browser_buffer`

These adapters project the same tensor cell into a durable or externally addressable storage surface. A workbook, file, persistent volume, or browser persistence layer is a backing surface, not a separate tensor identity.

### path_c — volatile software execution

Ordered adapter kinds:

1. `vm_memory`
2. `simulated_memory`
3. `software_memory`

These adapters permit immediate execution when physical and persistent surfaces are absent. The volume remains allocated and operational; only backing durability and hardware evidence differ.

## Selection algorithm

```text
for path in [path_a, path_b, path_c]:
    for adapter in path.declared_order:
        if adapter.available and adapter.contract_complete:
            select adapter
            stop evaluation
```

No input or state from an incomplete path is merged with another path unless a separately declared composite adapter contract explicitly authorizes it.

## Backing address rule

Every selected adapter derives its projection address from the canonical slot:

```text
A_backing(cell, adapter) = adapter.base + cell.canonical_slot * 4096
```

This preserves unique cell projection even when multiple coordinates share the same prime route residue.

## Invariants

```text
I1: coordinate identity is invariant across backing changes
I2: canonical slot is invariant across backing changes
I3: route residue is invariant across backing changes
I4: occupancy state is owned by the tensor volume, not by a backing adapter
I5: release/re-entry semantics are owned by the tensor volume
I6: backing selection is deterministic and ordered A -> B -> C
I7: physical projection is optional for volume existence
I8: a backing failure removes only that backing capability
I9: unavailable path A activates path B; unavailable A and B activate C
I10: all paths unavailable stops only binding, not the tensor identity
```

## Integration surfaces

The same tensor volume may be consumed by:

```text
software volume
simulated memory
workbook cells
file-backed storage
browser buffer
VM memory
physical frames
device/MMIO region
```

All consumers must preserve the same coordinate, slot, route, lineage, allocation, release, and receipt fields.
