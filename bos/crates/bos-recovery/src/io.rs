use bos_cap::{CapHandle, ExtentLease};
use sha2::{Digest, Sha256};

use crate::{RECOVERY_BLOCK_BYTES, RecoveryError, RecoveryRequest};

#[repr(C, align(4096))]
#[derive(Clone, Copy)]
pub struct RecoveryBlock {
    data: [u8; RECOVERY_BLOCK_BYTES],
}

impl RecoveryBlock {
    pub const ZERO: Self = Self {
        data: [0u8; RECOVERY_BLOCK_BYTES],
    };

    pub const fn as_bytes(&self) -> &[u8; RECOVERY_BLOCK_BYTES] {
        &self.data
    }

    pub fn as_mut_bytes(&mut self) -> &mut [u8; RECOVERY_BLOCK_BYTES] {
        &mut self.data
    }
}

impl Default for RecoveryBlock {
    fn default() -> Self {
        Self::ZERO
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExtentDescriptor {
    pub capability: CapHandle,
    pub device_identity: [u8; 32],
    pub namespace_id: u32,
    pub start_lba: u64,
    pub lba_count: u64,
    pub logical_block_size: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReadReceipt {
    descriptor: ExtentDescriptor,
    controller_epoch: u64,
    buffer_generation: u64,
    bytes_requested: u64,
    bytes_completed: u64,
    completion_status: i32,
}

impl ReadReceipt {
    /// Constructs a receipt after the implementing backend has observed an
    /// authoritative hardware completion.
    ///
    /// # Safety
    ///
    /// The caller must be part of the trusted backend and must guarantee that
    /// the supplied descriptor and completion fields were obtained from the
    /// exact capability-bound read represented by this receipt. Fabricating a
    /// successful receipt crosses the BOS protection boundary.
    #[allow(clippy::too_many_arguments)]
    pub unsafe fn from_trusted_completion(
        descriptor: ExtentDescriptor,
        controller_epoch: u64,
        buffer_generation: u64,
        bytes_requested: u64,
        bytes_completed: u64,
        completion_status: i32,
    ) -> Self {
        Self {
            descriptor,
            controller_epoch,
            buffer_generation,
            bytes_requested,
            bytes_completed,
            completion_status,
        }
    }

    pub const fn descriptor(&self) -> ExtentDescriptor {
        self.descriptor
    }

    pub const fn controller_epoch(&self) -> u64 {
        self.controller_epoch
    }

    pub const fn buffer_generation(&self) -> u64 {
        self.buffer_generation
    }

    pub const fn bytes_requested(&self) -> u64 {
        self.bytes_requested
    }

    pub const fn bytes_completed(&self) -> u64 {
        self.bytes_completed
    }

    pub const fn completion_status(&self) -> i32 {
        self.completion_status
    }

    pub(crate) fn verify(
        &self,
        lease: &ExtentLease<'_>,
        request: &RecoveryRequest,
    ) -> Result<(), RecoveryError> {
        if self.descriptor.capability != lease.handle()
            || self.descriptor.namespace_id != lease.namespace_id()
            || self.descriptor.start_lba != lease.start_lba()
            || self.descriptor.lba_count != lease.lba_count()
            || self.descriptor.logical_block_size != lease.logical_block_size()
            || self.descriptor.start_lba != request.start_lba
            || self.descriptor.lba_count != request.lba_count
            || self.descriptor.logical_block_size != request.logical_block_size
        {
            return Err(RecoveryError::ReadBindingMismatch);
        }
        let expected = request.total_bytes()?;
        if self.bytes_requested != expected {
            return Err(RecoveryError::ReadGeometryMismatch);
        }
        if self.completion_status != 0 {
            return Err(RecoveryError::BackendIo(self.completion_status));
        }
        if self.bytes_completed != self.bytes_requested {
            return Err(RecoveryError::ShortRead);
        }
        Ok(())
    }
}

pub struct ReadBatch<'a> {
    receipt: ReadReceipt,
    blocks: &'a [RecoveryBlock],
}

impl<'a> ReadBatch<'a> {
    /// # Safety
    ///
    /// `blocks` must contain exactly the buffers populated by the hardware
    /// operation represented by `receipt`, and they must remain immutable for
    /// the returned lifetime.
    pub unsafe fn from_trusted_completion(
        receipt: ReadReceipt,
        blocks: &'a [RecoveryBlock],
    ) -> Self {
        Self { receipt, blocks }
    }

    pub const fn receipt(&self) -> &ReadReceipt {
        &self.receipt
    }

    pub const fn blocks(&self) -> &'a [RecoveryBlock] {
        self.blocks
    }
}

/// Trusted adapter contract between the recovery gate and raw block I/O.
///
/// # Safety
///
/// An implementation is part of the trusted computing base. It must issue the
/// read only after validating the supplied generation-pinned lease, must not
/// substitute a different file/device/range, and must report exact completion.
pub unsafe trait CapabilityBoundBlockIo {
    fn read_exact<'a>(
        &'a mut self,
        lease: &ExtentLease<'_>,
        request: &RecoveryRequest,
    ) -> Result<ReadBatch<'a>, RecoveryError>;
}

pub fn derive_extent_map_root(descriptor: &ExtentDescriptor) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"BOS/EXTENT-MAP/v3");
    hasher.update(descriptor.capability.slot().to_be_bytes());
    hasher.update(descriptor.capability.generation().to_be_bytes());
    hasher.update(descriptor.device_identity);
    hasher.update(descriptor.namespace_id.to_be_bytes());
    hasher.update(descriptor.start_lba.to_be_bytes());
    hasher.update(descriptor.lba_count.to_be_bytes());
    hasher.update(descriptor.logical_block_size.to_be_bytes());
    hasher.finalize().into()
}
