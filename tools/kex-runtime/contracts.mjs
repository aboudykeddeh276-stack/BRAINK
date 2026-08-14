export const MACHINE_TEMPLATE_COORDINATE = 'KEX://MACHINE-TEMPLATE/HYPERPROCESSOR-V2';

export const HARDWARE_FAMILIES = Object.freeze({
  CPU: Object.freeze(['ISA', 'REGISTER_FILE', 'PRIVILEGE', 'EXECUTION']),
  MMU: Object.freeze(['ADDRESS_SPACE', 'PAGE_TABLE', 'TRANSLATION', 'PROTECTION']),
  MEMORY: Object.freeze(['RAM', 'ROM', 'NUMA_DESCRIPTOR', 'SNAPSHOT']),
  SYSTEM_BUS: Object.freeze(['MMIO', 'PORT_IO', 'ADDRESS_DECODE', 'HOTPLUG']),
  DMA_IOMMU: Object.freeze(['DMA', 'IOMMU', 'DEVICE_MEMORY_MAP']),
  INTERRUPT: Object.freeze(['IRQ_CONTROLLER', 'VECTOR_TABLE', 'ROUTING']),
  TIMER_CLOCK: Object.freeze(['MONOTONIC_CLOCK', 'TIMER', 'RTC', 'WATCHDOG']),
  NETWORK: Object.freeze(['VNIC', 'QUEUE', 'LINK_STATE', 'ROUTE_BINDING']),
  BLOCK: Object.freeze(['VBLOCK', 'NAMESPACE', 'SNAPSHOT', 'JOURNAL']),
  FIRMWARE: Object.freeze(['BOOT_ROM', 'NVRAM', 'DEVICE_TREE_OR_ACPI']),
  BOOT: Object.freeze(['LOADER', 'KERNEL_HANDOFF', 'INIT_STATE']),
  CONSOLE_DISPLAY: Object.freeze(['SERIAL', 'FRAMEBUFFER', 'INPUT']),
  ACCELERATOR: Object.freeze(['VECTOR', 'GPU_DESCRIPTOR', 'OFFLOAD_CONTRACT']),
  ENTROPY: Object.freeze(['RNG_INTERFACE', 'ENTROPY_STATE'])
});

export const HARDWARE_FAMILY_NAMES = Object.freeze(Object.keys(HARDWARE_FAMILIES));

export const CLOSURE_ORDER = Object.freeze([
  'CPU', 'MEMORY', 'SYSTEM_BUS', 'MMU', 'DMA_IOMMU', 'INTERRUPT', 'TIMER_CLOCK',
  'NETWORK', 'BLOCK', 'FIRMWARE', 'BOOT', 'CONSOLE_DISPLAY', 'ACCELERATOR', 'ENTROPY'
]);

export const MATERIALISATION_STATES = Object.freeze([
  'VIRTUAL_ADDRESSABLE',
  'CARRIER_READY',
  'MATERIALISATION_REQUESTED',
  'MATERIALISED',
  'READBACK_VERIFIED',
  'MATERIALISATION_LOST',
  'REHYDRATED',
  'REJOINED'
]);

export const GLOBAL_INVARIANTS = Object.freeze({
  physical_host_in_lineage: false,
  provider_in_lineage: false,
  virtual_machine_can_be_parent_carrier: true,
  failover_is_rehydration: true,
  failback_required: false,
  machine_template_shared: true,
  logical_machine_count_independent_of_process_count: true,
  hardware_interface_equivalence_is_not_performance_equivalence: true,
  entropy_is_transition_evidence_not_identity_authority: true,
  endpoint_digest_is_not_kex_authority: true
});

export function normalizeSegment(value) {
  return String(value).trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'STATE';
}

export function makeMachineStateRefs(coordinate) {
  return Object.freeze({
    cpu_state_ref: `${coordinate}/STATE/CPU`,
    mmu_state_ref: `${coordinate}/STATE/MMU`,
    memory_state_ref: `${coordinate}/STATE/MEMORY`,
    bus_state_ref: `${coordinate}/STATE/BUS`,
    dma_state_ref: `${coordinate}/STATE/DMA-IOMMU`,
    interrupt_state_ref: `${coordinate}/STATE/IRQ`,
    clock_state_ref: `${coordinate}/STATE/CLOCK`,
    network_state_ref: `${coordinate}/STATE/NETWORK`,
    storage_state_ref: `${coordinate}/STATE/BLOCK`,
    firmware_state_ref: `${coordinate}/STATE/FIRMWARE`,
    boot_state_ref: `${coordinate}/STATE/BOOT`,
    console_state_ref: `${coordinate}/STATE/CONSOLE`,
    accelerator_state_ref: `${coordinate}/STATE/ACCELERATOR`,
    entropy_state_ref: `${coordinate}/STATE/ENTROPY`
  });
}
