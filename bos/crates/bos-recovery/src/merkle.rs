use sha2::{Digest, Sha256};

use crate::{MAX_RECOVERY_BLOCKS, RecoveryBlock, RecoveryError, RecoveryRequest};

pub fn compute_geometry_bound_merkle_root(
    request: &RecoveryRequest,
    blocks: &[RecoveryBlock],
) -> Result<[u8; 32], RecoveryError> {
    request.validate()?;
    let expected_count = request.block_count()?;
    if expected_count == 0 {
        return Err(RecoveryError::EmptyRange);
    }
    if expected_count > MAX_RECOVERY_BLOCKS {
        return Err(RecoveryError::TooManyBlocks);
    }
    if blocks.len() != expected_count {
        return Err(RecoveryError::ReadGeometryMismatch);
    }

    let mut level = [[0u8; 32]; MAX_RECOVERY_BLOCKS];
    let mut index = 0usize;
    while index < expected_count {
        let length = request.block_len(index)?;
        let absolute_lba = request.block_start_lba(index)?;
        let mut leaf = Sha256::new();
        leaf.update(b"BOS/LEAF/v3");
        leaf.update(request.cluster_id);
        leaf.update(request.volume_id);
        leaf.update((index as u32).to_be_bytes());
        leaf.update(absolute_lba.to_be_bytes());
        leaf.update((length as u32).to_be_bytes());
        leaf.update(&blocks[index].as_bytes()[..length]);
        level[index] = leaf.finalize().into();
        index += 1;
    }

    let mut level_size = expected_count;
    let mut tree_level = 0u32;
    while level_size > 1 {
        let mut read_index = 0usize;
        let mut write_index = 0usize;
        while read_index < level_size {
            let left = level[read_index];
            let right = if read_index + 1 < level_size {
                level[read_index + 1]
            } else {
                left
            };
            let mut node = Sha256::new();
            node.update(b"BOS/NODE/v3");
            node.update(tree_level.to_be_bytes());
            node.update(left);
            node.update(right);
            level[write_index] = node.finalize().into();
            write_index += 1;
            read_index += 2;
        }
        level_size = write_index;
        tree_level = tree_level
            .checked_add(1)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
    }

    let mut envelope = Sha256::new();
    envelope.update(b"BOS/DATA-ROOT/v3");
    envelope.update(request.cluster_id);
    envelope.update(request.volume_id);
    envelope.update((expected_count as u32).to_be_bytes());
    envelope.update(request.total_bytes()?.to_be_bytes());
    envelope.update(request.start_lba.to_be_bytes());
    envelope.update(request.lba_count.to_be_bytes());
    envelope.update(request.logical_block_size.to_be_bytes());
    envelope.update(level[0]);
    Ok(envelope.finalize().into())
}
