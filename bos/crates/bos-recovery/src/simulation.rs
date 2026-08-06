//! Deterministic in-memory backends for executable recovery proofs.
//!
//! These types are deliberately named simulation backends. They do not claim
//! physical-media, TPM, or power-loss durability.

use bos_cap::{CapHandle, ExtentLease};

use crate::{
    AnchorState, CapabilityBoundBlockIo, DurableRootStore, ExtentDescriptor, HardgateAnchor,
    MAX_RECOVERY_BLOCKS, ReadBatch, ReadReceipt, RecoveryBlock, RecoveryError, RecoveryRequest,
    RootSlot, StateCapsuleV3, VerifiedCapsule,
};

pub struct MemoryBlockIo {
    blocks: [RecoveryBlock; MAX_RECOVERY_BLOCKS],
    block_count: usize,
    device_identity: [u8; 32],
    namespace_id: u32,
    controller_epoch: u64,
    buffer_generation: u64,
    forced_status: i32,
    completed_bytes_override: Option<u64>,
}

impl MemoryBlockIo {
    pub fn new(
        blocks: [RecoveryBlock; MAX_RECOVERY_BLOCKS],
        block_count: usize,
        device_identity: [u8; 32],
        namespace_id: u32,
    ) -> Result<Self, RecoveryError> {
        if block_count == 0 || block_count > MAX_RECOVERY_BLOCKS {
            return Err(RecoveryError::InvalidRequest);
        }
        Ok(Self {
            blocks,
            block_count,
            device_identity,
            namespace_id,
            controller_epoch: 1,
            buffer_generation: 1,
            forced_status: 0,
            completed_bytes_override: None,
        })
    }

    pub fn blocks(&self) -> &[RecoveryBlock] {
        &self.blocks[..self.block_count]
    }

    pub fn blocks_mut(&mut self) -> &mut [RecoveryBlock] {
        &mut self.blocks[..self.block_count]
    }

    pub fn set_forced_status(&mut self, status: i32) {
        self.forced_status = status;
    }

    pub fn set_completed_bytes_override(&mut self, bytes: Option<u64>) {
        self.completed_bytes_override = bytes;
    }

    pub fn descriptor_for(
        &self,
        capability: CapHandle,
        request: &RecoveryRequest,
    ) -> ExtentDescriptor {
        ExtentDescriptor {
            capability,
            device_identity: self.device_identity,
            namespace_id: self.namespace_id,
            start_lba: request.start_lba,
            lba_count: request.lba_count,
            logical_block_size: request.logical_block_size,
        }
    }
}

// SAFETY: This simulation backend returns exactly its immutable, fixed buffer
// array and derives the receipt from the supplied generation-pinned lease.
unsafe impl CapabilityBoundBlockIo for MemoryBlockIo {
    fn read_exact<'a>(
        &'a mut self,
        lease: &ExtentLease<'_>,
        request: &RecoveryRequest,
    ) -> Result<ReadBatch<'a>, RecoveryError> {
        request.validate()?;
        if request.block_count()? != self.block_count
            || lease.namespace_id() != self.namespace_id
            || lease.start_lba() != request.start_lba
            || lease.lba_count() != request.lba_count
            || lease.logical_block_size() != request.logical_block_size
        {
            return Err(RecoveryError::ReadBindingMismatch);
        }
        let requested = request.total_bytes()?;
        let completed = self.completed_bytes_override.unwrap_or(requested);
        let descriptor = self.descriptor_for(lease.handle(), request);
        // SAFETY: This backend owns the returned fixed buffers and has just
        // bound the receipt to the exact lease and request above.
        let receipt = unsafe {
            ReadReceipt::from_trusted_completion(
                descriptor,
                self.controller_epoch,
                self.buffer_generation,
                requested,
                completed,
                self.forced_status,
            )
        };
        // SAFETY: `blocks` is the exact immutable buffer range represented by
        // the receipt and is borrowed for the returned lifetime.
        Ok(
            unsafe {
                ReadBatch::from_trusted_completion(receipt, &self.blocks[..self.block_count])
            },
        )
    }
}

pub struct MemoryRootStore {
    active: RootSlot,
    slot_a: Option<StateCapsuleV3>,
    slot_b: Option<StateCapsuleV3>,
    prepared_slot: Option<RootSlot>,
    selector_pending: Option<RootSlot>,
    selector_sequence: u64,
}

impl MemoryRootStore {
    pub const fn new(active: RootSlot) -> Self {
        Self {
            active,
            slot_a: None,
            slot_b: None,
            prepared_slot: None,
            selector_pending: None,
            selector_sequence: 0,
        }
    }

    pub fn committed_capsule(&self, slot: RootSlot) -> Option<&StateCapsuleV3> {
        match slot {
            RootSlot::A => self.slot_a.as_ref(),
            RootSlot::B => self.slot_b.as_ref(),
        }
    }

    pub const fn selector_sequence(&self) -> u64 {
        self.selector_sequence
    }
}

impl DurableRootStore for MemoryRootStore {
    fn active_slot(&self) -> Result<RootSlot, RecoveryError> {
        Ok(self.active)
    }

    fn write_prepared(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
        capsule: &StateCapsuleV3,
    ) -> Result<(), RecoveryError> {
        if capsule.capsule_hash()? != verified.capsule_hash()
            || capsule.state_root != verified.state_root()
        {
            return Err(RecoveryError::RootStoreFailure);
        }
        match slot {
            RootSlot::A => self.slot_a = Some(*capsule),
            RootSlot::B => self.slot_b = Some(*capsule),
        }
        self.prepared_slot = Some(slot);
        Ok(())
    }

    fn flush_root_slot(&mut self, slot: RootSlot) -> Result<(), RecoveryError> {
        if self.prepared_slot != Some(slot) {
            return Err(RecoveryError::RootStoreFailure);
        }
        Ok(())
    }

    fn publish_selector(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
    ) -> Result<(), RecoveryError> {
        if self.prepared_slot != Some(slot) {
            return Err(RecoveryError::SelectorFailure);
        }
        self.selector_pending = Some(slot);
        self.selector_sequence = verified.sequence();
        Ok(())
    }

    fn flush_selector(&mut self) -> Result<(), RecoveryError> {
        let next = self
            .selector_pending
            .take()
            .ok_or(RecoveryError::SelectorFailure)?;
        self.active = next;
        self.prepared_slot = None;
        Ok(())
    }
}

pub struct MemoryHardgateAnchor {
    state: AnchorState,
}

impl MemoryHardgateAnchor {
    pub const fn new(state: AnchorState) -> Self {
        Self { state }
    }
}

impl HardgateAnchor for MemoryHardgateAnchor {
    fn current(&self) -> Result<AnchorState, RecoveryError> {
        Ok(self.state)
    }

    fn advance(
        &mut self,
        expected: &AnchorState,
        next: &VerifiedCapsule,
    ) -> Result<(), RecoveryError> {
        if &self.state != expected {
            return Err(RecoveryError::AnchorConflict);
        }
        if next.cluster_id() != expected.cluster_id
            || next.volume_id() != expected.volume_id
            || next.membership_epoch() != expected.membership_epoch
            || next.sequence() <= expected.sequence
            || next.parent_capsule_hash() != expected.capsule_hash
            || next.parent_state_root() != expected.state_root
        {
            return Err(RecoveryError::AnchorConflict);
        }
        self.state = AnchorState {
            cluster_id: next.cluster_id(),
            volume_id: next.volume_id(),
            membership_epoch: next.membership_epoch(),
            sequence: next.sequence(),
            capsule_hash: next.capsule_hash(),
            state_root: next.state_root(),
        };
        Ok(())
    }
}
