import { HARDWARE_FAMILY_NAMES } from './contracts.mjs';

export class RehydrationEngine {
  constructor({ graph, ledger, entropy }) {
    this.graph = graph;
    this.ledger = ledger;
    this.entropy = entropy;
    this.materialisations = new Map();
    this.counter = 0;
  }

  registerVirtualMaterialisation({ lineageCoordinate, carrierCoordinate, stateRefs, verification = 'VIRTUAL_ONLY' }) {
    const carrier = this.graph.spaces.get(carrierCoordinate);
    if (!carrier?.hardwareComplete) throw new Error('Carrier is not hardware-complete');
    const id = `${lineageCoordinate}/MATERIALISATION/${String(++this.counter).padStart(8, '0')}`;
    const record = Object.freeze({
      materialisation_id: id,
      lineage_coordinate: lineageCoordinate,
      carrier_machine: carrierCoordinate,
      state_refs: stateRefs,
      materialisation_state: 'MATERIALISED',
      verification_state: verification,
      carrier_in_lineage: false
    });
    this.materialisations.set(id, record);
    this.ledger.append('REGISTER_MATERIALISATION', record);
    return record;
  }

  selectRandomDistinct(candidates, count, label) {
    if (!Number.isInteger(count) || count < 1) throw new Error('count must be positive integer');
    if (candidates.length < count) throw new Error(`Need ${count} carriers, have ${candidates.length}`);
    const pool = [...candidates];
    const selected = [];
    for (let i = 0; i < count; i += 1) {
      const entropy = this.entropy.choose(pool.length, `${label}:${i}`);
      const [carrier] = pool.splice(entropy.value, 1);
      selected.push({ carrier, entropy });
    }
    return selected;
  }

  rehydrate({ materialisation, fanout = 1, requiredFamilies = HARDWARE_FAMILY_NAMES, reason = 'MATERIALISATION_LOSS' }) {
    const sourceCarrier = materialisation.carrier_machine;
    this.ledger.append('MATERIALISATION_LOSS', {
      materialisation_id: materialisation.materialisation_id,
      lineage_coordinate: materialisation.lineage_coordinate,
      source_carrier: sourceCarrier,
      reason
    });

    const candidates = this.graph.eligibleCarriers({
      exclude: new Set([sourceCarrier]),
      requiredFamilies
    });

    const selected = this.selectRandomDistinct(candidates, fanout, `REHYDRATE:${materialisation.lineage_coordinate}`);
    return selected.map(({ carrier, entropy }) => {
      const id = `${materialisation.lineage_coordinate}/REHYDRATED/${String(++this.counter).padStart(8, '0')}`;
      const receipt = Object.freeze({
        materialisation_id: id,
        lineage_coordinate: materialisation.lineage_coordinate,
        prior_materialisation: materialisation.materialisation_id,
        source_carrier: sourceCarrier,
        target_carrier: carrier.coordinate,
        target_generation: carrier.generation,
        machine_template_ref: carrier.templateRef,
        state_refs: materialisation.state_refs,
        transition: 'REHYDRATES_TO',
        entropy_observation: entropy,
        lineage_rewritten: false,
        physical_host_ancestor: false,
        verification_state: 'VIRTUAL_REHYDRATION_COMPLETE_EXTERNAL_READBACK_PENDING'
      });
      this.materialisations.set(id, receipt);
      this.ledger.append('REHYDRATE_LINEAGE', receipt);
      return receipt;
    });
  }

  verifyExternalReadback(materialisationId, receipt) {
    if (!receipt || receipt.scope !== 'EXTERNAL') throw new Error('External readback must have scope EXTERNAL');
    const existing = this.materialisations.get(materialisationId);
    if (!existing) throw new Error(`Unknown materialisation ${materialisationId}`);
    const updated = Object.freeze({
      ...existing,
      verification_state: 'READBACK_VERIFIED',
      external_readback: Object.freeze({ ...receipt })
    });
    this.materialisations.set(materialisationId, updated);
    this.ledger.append('VERIFY_EXTERNAL_READBACK', {
      materialisation_id: materialisationId,
      observer: receipt.observer ?? 'UNSPECIFIED',
      authority: receipt.authority ?? 'UNSPECIFIED',
      receipt: receipt.receipt ?? null
    });
    return updated;
  }
}
