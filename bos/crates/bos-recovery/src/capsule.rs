use sha2::{Digest, Sha256};

use crate::{MAX_QUORUM_NODES, RecoveryError};

pub const CAPSULE_MAGIC: [u8; 8] = *b"BOSCAPS\x03";
pub const CAPSULE_FORMAT_VERSION: u16 = 3;
pub const HASH_ALGORITHM_SHA256: u16 = 1;
pub const SIGNATURE_ALGORITHM_ED25519: u16 = 1;
pub const ED25519_SIGNATURE_BYTES: usize = 64;
pub const CAPSULE_UNSIGNED_LEN: usize = 328;
pub const CAPSULE_ENCODED_LEN: usize = 912;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CommitCertificate {
    membership_root: [u8; 32],
    signer_bitmap: u16,
    signatures: [[u8; ED25519_SIGNATURE_BYTES]; MAX_QUORUM_NODES],
}

impl CommitCertificate {
    pub const fn new(membership_root: [u8; 32]) -> Self {
        Self {
            membership_root,
            signer_bitmap: 0,
            signatures: [[0u8; ED25519_SIGNATURE_BYTES]; MAX_QUORUM_NODES],
        }
    }

    pub fn set_signature(
        &mut self,
        member_position: usize,
        signature: [u8; ED25519_SIGNATURE_BYTES],
    ) -> Result<(), RecoveryError> {
        if member_position >= MAX_QUORUM_NODES {
            return Err(RecoveryError::SignerOutsideMembership);
        }
        self.signatures[member_position] = signature;
        self.signer_bitmap |= 1u16 << member_position;
        Ok(())
    }

    pub fn clear_signature(&mut self, member_position: usize) -> Result<(), RecoveryError> {
        if member_position >= MAX_QUORUM_NODES {
            return Err(RecoveryError::SignerOutsideMembership);
        }
        self.signatures[member_position] = [0u8; ED25519_SIGNATURE_BYTES];
        self.signer_bitmap &= !(1u16 << member_position);
        Ok(())
    }

    pub const fn membership_root(&self) -> [u8; 32] {
        self.membership_root
    }

    pub const fn signer_bitmap(&self) -> u16 {
        self.signer_bitmap
    }

    pub const fn signature_at(
        &self,
        member_position: usize,
    ) -> Option<&[u8; ED25519_SIGNATURE_BYTES]> {
        if member_position < MAX_QUORUM_NODES {
            Some(&self.signatures[member_position])
        } else {
            None
        }
    }

    pub const fn signatures(&self) -> &[[u8; ED25519_SIGNATURE_BYTES]; MAX_QUORUM_NODES] {
        &self.signatures
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct StateCapsuleV3 {
    pub cluster_id: [u8; 16],
    pub volume_id: [u8; 16],
    pub membership_epoch: u64,
    pub consensus_view: u64,
    pub capsule_sequence: u64,
    pub parent_capsule_hash: [u8; 32],
    pub parent_state_root: [u8; 32],
    pub data_merkle_root: [u8; 32],
    pub manifest_root: [u8; 32],
    pub extent_map_root: [u8; 32],
    pub state_root: [u8; 32],
    pub start_lba: u64,
    pub logical_block_count: u64,
    pub logical_block_size: u32,
    pub total_state_bytes: u64,
    pub certificate: CommitCertificate,
}

impl StateCapsuleV3 {
    pub fn encode_unsigned_into(
        &self,
        output: &mut [u8; CAPSULE_UNSIGNED_LEN],
    ) -> Result<(), RecoveryError> {
        let mut writer = Encoder::new(output);
        writer.put(&CAPSULE_MAGIC)?;
        writer.put_u32(CAPSULE_ENCODED_LEN as u32)?;
        writer.put_u16(CAPSULE_FORMAT_VERSION)?;
        writer.put_u16(HASH_ALGORITHM_SHA256)?;
        writer.put_u16(SIGNATURE_ALGORITHM_ED25519)?;
        writer.put_u16(0)?;
        writer.put(&self.cluster_id)?;
        writer.put(&self.volume_id)?;
        writer.put_u64(self.membership_epoch)?;
        writer.put_u64(self.consensus_view)?;
        writer.put_u64(self.capsule_sequence)?;
        writer.put(&self.parent_capsule_hash)?;
        writer.put(&self.parent_state_root)?;
        writer.put(&self.data_merkle_root)?;
        writer.put(&self.manifest_root)?;
        writer.put(&self.extent_map_root)?;
        writer.put(&self.state_root)?;
        writer.put_u64(self.start_lba)?;
        writer.put_u64(self.logical_block_count)?;
        writer.put_u32(self.logical_block_size)?;
        writer.put_u64(self.total_state_bytes)?;
        writer.put(&self.certificate.membership_root)?;
        writer.finish()
    }

    pub fn encode_into(&self, output: &mut [u8; CAPSULE_ENCODED_LEN]) -> Result<(), RecoveryError> {
        let mut unsigned = [0u8; CAPSULE_UNSIGNED_LEN];
        self.encode_unsigned_into(&mut unsigned)?;

        let mut writer = Encoder::new(output);
        writer.put(&unsigned)?;
        writer.put_u16(self.certificate.signer_bitmap)?;
        writer.put(&[0u8; 6])?;
        let mut index = 0usize;
        while index < MAX_QUORUM_NODES {
            writer.put(&self.certificate.signatures[index])?;
            index += 1;
        }
        writer.finish()
    }

    pub fn decode(input: &[u8]) -> Result<Self, RecoveryError> {
        if input.len() != CAPSULE_ENCODED_LEN {
            return Err(RecoveryError::InvalidCapsuleLength);
        }
        let mut reader = Decoder::new(input);
        if reader.take_array::<8>()? != CAPSULE_MAGIC {
            return Err(RecoveryError::InvalidCapsuleMagic);
        }
        if reader.take_u32()? != CAPSULE_ENCODED_LEN as u32 {
            return Err(RecoveryError::InvalidCapsuleLength);
        }
        if reader.take_u16()? != CAPSULE_FORMAT_VERSION {
            return Err(RecoveryError::UnsupportedCapsuleVersion);
        }
        if reader.take_u16()? != HASH_ALGORITHM_SHA256 {
            return Err(RecoveryError::UnsupportedHashAlgorithm);
        }
        if reader.take_u16()? != SIGNATURE_ALGORITHM_ED25519 {
            return Err(RecoveryError::UnsupportedSignatureAlgorithm);
        }
        if reader.take_u16()? != 0 {
            return Err(RecoveryError::NonCanonicalEncoding);
        }

        let cluster_id = reader.take_array::<16>()?;
        let volume_id = reader.take_array::<16>()?;
        let membership_epoch = reader.take_u64()?;
        let consensus_view = reader.take_u64()?;
        let capsule_sequence = reader.take_u64()?;
        let parent_capsule_hash = reader.take_array::<32>()?;
        let parent_state_root = reader.take_array::<32>()?;
        let data_merkle_root = reader.take_array::<32>()?;
        let manifest_root = reader.take_array::<32>()?;
        let extent_map_root = reader.take_array::<32>()?;
        let state_root = reader.take_array::<32>()?;
        let start_lba = reader.take_u64()?;
        let logical_block_count = reader.take_u64()?;
        let logical_block_size = reader.take_u32()?;
        let total_state_bytes = reader.take_u64()?;
        let membership_root = reader.take_array::<32>()?;
        let signer_bitmap = reader.take_u16()?;
        if reader.take_array::<6>()? != [0u8; 6] {
            return Err(RecoveryError::NonCanonicalEncoding);
        }

        let mut signatures = [[0u8; ED25519_SIGNATURE_BYTES]; MAX_QUORUM_NODES];
        let mut index = 0usize;
        while index < MAX_QUORUM_NODES {
            signatures[index] = reader.take_array::<ED25519_SIGNATURE_BYTES>()?;
            index += 1;
        }
        reader.finish()?;

        Ok(Self {
            cluster_id,
            volume_id,
            membership_epoch,
            consensus_view,
            capsule_sequence,
            parent_capsule_hash,
            parent_state_root,
            data_merkle_root,
            manifest_root,
            extent_map_root,
            state_root,
            start_lba,
            logical_block_count,
            logical_block_size,
            total_state_bytes,
            certificate: CommitCertificate {
                membership_root,
                signer_bitmap,
                signatures,
            },
        })
    }

    pub fn proposal_digest(&self) -> Result<[u8; 32], RecoveryError> {
        let mut encoded = [0u8; CAPSULE_UNSIGNED_LEN];
        self.encode_unsigned_into(&mut encoded)?;
        let mut hasher = Sha256::new();
        hasher.update(b"BOS/CAPSULE-PROPOSAL/v3");
        hasher.update(encoded);
        Ok(hasher.finalize().into())
    }

    pub fn capsule_hash(&self) -> Result<[u8; 32], RecoveryError> {
        let mut encoded = [0u8; CAPSULE_ENCODED_LEN];
        self.encode_into(&mut encoded)?;
        let mut hasher = Sha256::new();
        hasher.update(b"BOS/CAPSULE-FULL/v3");
        hasher.update(encoded);
        Ok(hasher.finalize().into())
    }
}

pub fn derive_state_root(capsule: &StateCapsuleV3) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"BOS/STATE/v3");
    hasher.update(capsule.cluster_id);
    hasher.update(capsule.volume_id);
    hasher.update(capsule.membership_epoch.to_be_bytes());
    hasher.update(capsule.consensus_view.to_be_bytes());
    hasher.update(capsule.capsule_sequence.to_be_bytes());
    hasher.update(capsule.parent_capsule_hash);
    hasher.update(capsule.parent_state_root);
    hasher.update(capsule.data_merkle_root);
    hasher.update(capsule.manifest_root);
    hasher.update(capsule.extent_map_root);
    hasher.update(capsule.start_lba.to_be_bytes());
    hasher.update(capsule.logical_block_count.to_be_bytes());
    hasher.update(capsule.logical_block_size.to_be_bytes());
    hasher.update(capsule.total_state_bytes.to_be_bytes());
    hasher.finalize().into()
}

struct Encoder<'a> {
    output: &'a mut [u8],
    offset: usize,
}

impl<'a> Encoder<'a> {
    const fn new(output: &'a mut [u8]) -> Self {
        Self { output, offset: 0 }
    }

    fn put(&mut self, bytes: &[u8]) -> Result<(), RecoveryError> {
        let end = self
            .offset
            .checked_add(bytes.len())
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        let destination = self
            .output
            .get_mut(self.offset..end)
            .ok_or(RecoveryError::InvalidCapsuleLength)?;
        destination.copy_from_slice(bytes);
        self.offset = end;
        Ok(())
    }

    fn put_u16(&mut self, value: u16) -> Result<(), RecoveryError> {
        self.put(&value.to_be_bytes())
    }

    fn put_u32(&mut self, value: u32) -> Result<(), RecoveryError> {
        self.put(&value.to_be_bytes())
    }

    fn put_u64(&mut self, value: u64) -> Result<(), RecoveryError> {
        self.put(&value.to_be_bytes())
    }

    fn finish(self) -> Result<(), RecoveryError> {
        if self.offset == self.output.len() {
            Ok(())
        } else {
            Err(RecoveryError::InvalidCapsuleLength)
        }
    }
}

struct Decoder<'a> {
    input: &'a [u8],
    offset: usize,
}

impl<'a> Decoder<'a> {
    const fn new(input: &'a [u8]) -> Self {
        Self { input, offset: 0 }
    }

    fn take_array<const N: usize>(&mut self) -> Result<[u8; N], RecoveryError> {
        let end = self
            .offset
            .checked_add(N)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        let source = self
            .input
            .get(self.offset..end)
            .ok_or(RecoveryError::InvalidCapsuleLength)?;
        let mut output = [0u8; N];
        output.copy_from_slice(source);
        self.offset = end;
        Ok(output)
    }

    fn take_u16(&mut self) -> Result<u16, RecoveryError> {
        Ok(u16::from_be_bytes(self.take_array::<2>()?))
    }

    fn take_u32(&mut self) -> Result<u32, RecoveryError> {
        Ok(u32::from_be_bytes(self.take_array::<4>()?))
    }

    fn take_u64(&mut self) -> Result<u64, RecoveryError> {
        Ok(u64::from_be_bytes(self.take_array::<8>()?))
    }

    fn finish(self) -> Result<(), RecoveryError> {
        if self.offset == self.input.len() {
            Ok(())
        } else {
            Err(RecoveryError::NonCanonicalEncoding)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> StateCapsuleV3 {
        let certificate = CommitCertificate::new([9u8; 32]);
        let mut capsule = StateCapsuleV3 {
            cluster_id: [1u8; 16],
            volume_id: [2u8; 16],
            membership_epoch: 3,
            consensus_view: 4,
            capsule_sequence: 5,
            parent_capsule_hash: [6u8; 32],
            parent_state_root: [7u8; 32],
            data_merkle_root: [8u8; 32],
            manifest_root: [10u8; 32],
            extent_map_root: [11u8; 32],
            state_root: [0u8; 32],
            start_lba: 100,
            logical_block_count: 2,
            logical_block_size: 4096,
            total_state_bytes: 8192,
            certificate,
        };
        capsule.state_root = derive_state_root(&capsule);
        capsule
    }

    #[test]
    fn canonical_round_trip_is_exact() {
        let capsule = sample();
        let mut encoded = [0u8; CAPSULE_ENCODED_LEN];
        capsule.encode_into(&mut encoded).unwrap();
        let decoded = StateCapsuleV3::decode(&encoded).unwrap();
        assert_eq!(decoded, capsule);
        assert_eq!(
            decoded.capsule_hash().unwrap(),
            capsule.capsule_hash().unwrap()
        );
    }

    #[test]
    fn rejects_noncanonical_reserved_bytes() {
        let capsule = sample();
        let mut encoded = [0u8; CAPSULE_ENCODED_LEN];
        capsule.encode_into(&mut encoded).unwrap();
        encoded[330] = 1;
        assert_eq!(
            StateCapsuleV3::decode(&encoded).err(),
            Some(RecoveryError::NonCanonicalEncoding)
        );
    }
}
