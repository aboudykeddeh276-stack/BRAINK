use crate::RecoveryError;

pub const RECOVERY_BLOCK_BYTES: usize = 4096;
pub const MAX_RECOVERY_BLOCKS: usize = 32;
pub const MAX_QUORUM_NODES: usize = 9;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RecoveryRequest {
    pub cluster_id: [u8; 16],
    pub volume_id: [u8; 16],
    pub start_lba: u64,
    pub lba_count: u64,
    pub logical_block_size: u32,
}

impl RecoveryRequest {
    pub fn validate(&self) -> Result<(), RecoveryError> {
        if self.lba_count == 0 {
            return Err(RecoveryError::EmptyRange);
        }
        if self.logical_block_size == 0
            || self.logical_block_size as usize > RECOVERY_BLOCK_BYTES
            || RECOVERY_BLOCK_BYTES % self.logical_block_size as usize != 0
        {
            return Err(RecoveryError::InvalidRequest);
        }
        let _ = self
            .start_lba
            .checked_add(self.lba_count)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        let total_bytes = self.total_bytes()?;
        if total_bytes == 0 {
            return Err(RecoveryError::EmptyRange);
        }
        if self.block_count()? > MAX_RECOVERY_BLOCKS {
            return Err(RecoveryError::TooManyBlocks);
        }
        Ok(())
    }

    pub fn total_bytes(&self) -> Result<u64, RecoveryError> {
        self.lba_count
            .checked_mul(u64::from(self.logical_block_size))
            .ok_or(RecoveryError::ArithmeticOverflow)
    }

    pub fn block_count(&self) -> Result<usize, RecoveryError> {
        let bytes = self.total_bytes()?;
        let block = RECOVERY_BLOCK_BYTES as u64;
        let rounded = bytes
            .checked_add(block - 1)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        usize::try_from(rounded / block).map_err(|_| RecoveryError::TooManyBlocks)
    }

    pub fn block_len(&self, block_index: usize) -> Result<usize, RecoveryError> {
        let count = self.block_count()?;
        if block_index >= count {
            return Err(RecoveryError::InvalidRequest);
        }
        let consumed = (block_index as u64)
            .checked_mul(RECOVERY_BLOCK_BYTES as u64)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        let remaining = self
            .total_bytes()?
            .checked_sub(consumed)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        Ok(core::cmp::min(remaining, RECOVERY_BLOCK_BYTES as u64) as usize)
    }

    pub fn block_start_lba(&self, block_index: usize) -> Result<u64, RecoveryError> {
        let byte_offset = (block_index as u64)
            .checked_mul(RECOVERY_BLOCK_BYTES as u64)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        let lba_offset = byte_offset / u64::from(self.logical_block_size);
        self.start_lba
            .checked_add(lba_offset)
            .ok_or(RecoveryError::ArithmeticOverflow)
    }
}
