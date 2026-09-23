use ed25519_dalek::{Signature, VerifyingKey};
use sha2::{Digest, Sha256};

use crate::{MAX_QUORUM_NODES, RecoveryError, StateCapsuleV3};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FaultModel {
    Crash,
    Byzantine { max_faults: u8 },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ConsensusPolicy {
    n_nodes: u8,
    k_threshold: u8,
    fault_model: FaultModel,
}

impl ConsensusPolicy {
    pub fn new(
        n_nodes: u8,
        k_threshold: u8,
        fault_model: FaultModel,
    ) -> Result<Self, RecoveryError> {
        if n_nodes == 0
            || n_nodes as usize > MAX_QUORUM_NODES
            || k_threshold == 0
            || k_threshold > n_nodes
        {
            return Err(RecoveryError::QuorumPolicyInvalid);
        }

        match fault_model {
            FaultModel::Crash => {
                if u16::from(k_threshold) * 2 <= u16::from(n_nodes) {
                    return Err(RecoveryError::QuorumPolicyInvalid);
                }
            }
            FaultModel::Byzantine { max_faults } => {
                let minimum_nodes = u16::from(max_faults)
                    .checked_mul(3)
                    .and_then(|value| value.checked_add(1))
                    .ok_or(RecoveryError::QuorumPolicyInvalid)?;
                let intersection = u16::from(k_threshold)
                    .checked_mul(2)
                    .and_then(|value| value.checked_sub(u16::from(n_nodes)))
                    .ok_or(RecoveryError::QuorumPolicyInvalid)?;
                if u16::from(n_nodes) < minimum_nodes || intersection <= u16::from(max_faults) {
                    return Err(RecoveryError::QuorumPolicyInvalid);
                }
            }
        }

        Ok(Self {
            n_nodes,
            k_threshold,
            fault_model,
        })
    }

    pub const fn n_nodes(self) -> u8 {
        self.n_nodes
    }

    pub const fn k_threshold(self) -> u8 {
        self.k_threshold
    }

    pub const fn fault_model(self) -> FaultModel {
        self.fault_model
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemberRecord {
    pub node_id: u8,
    pub active: bool,
    pub verifying_key: [u8; 32],
}

impl MemberRecord {
    pub const EMPTY: Self = Self {
        node_id: 0,
        active: false,
        verifying_key: [0u8; 32],
    };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MembershipManifest {
    cluster_id: [u8; 16],
    epoch: u64,
    node_count: u8,
    members: [MemberRecord; MAX_QUORUM_NODES],
}

impl MembershipManifest {
    pub fn new(
        cluster_id: [u8; 16],
        epoch: u64,
        node_count: u8,
        members: [MemberRecord; MAX_QUORUM_NODES],
    ) -> Result<Self, RecoveryError> {
        let manifest = Self {
            cluster_id,
            epoch,
            node_count,
            members,
        };
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn validate(&self) -> Result<(), RecoveryError> {
        if self.node_count == 0 || self.node_count as usize > MAX_QUORUM_NODES {
            return Err(RecoveryError::InvalidMembership);
        }

        let count = self.node_count as usize;
        let mut index = 0usize;
        while index < count {
            let member = self.members[index];
            if !member.active || member.node_id == 0 || member.node_id > self.node_count {
                return Err(RecoveryError::InvalidNodeId);
            }
            let key = VerifyingKey::from_bytes(&member.verifying_key)
                .map_err(|_| RecoveryError::InvalidPublicKey)?;
            if key.is_weak() {
                return Err(RecoveryError::InvalidPublicKey);
            }

            let mut previous = 0usize;
            while previous < index {
                if self.members[previous].node_id == member.node_id {
                    return Err(RecoveryError::DuplicateNodeId);
                }
                if self.members[previous].verifying_key == member.verifying_key {
                    return Err(RecoveryError::DuplicatePublicKey);
                }
                previous += 1;
            }
            index += 1;
        }

        while index < MAX_QUORUM_NODES {
            if self.members[index] != MemberRecord::EMPTY {
                return Err(RecoveryError::NonCanonicalEncoding);
            }
            index += 1;
        }

        Ok(())
    }

    pub const fn cluster_id(&self) -> [u8; 16] {
        self.cluster_id
    }

    pub const fn epoch(&self) -> u64 {
        self.epoch
    }

    pub const fn node_count(&self) -> u8 {
        self.node_count
    }

    pub const fn member_at(&self, position: usize) -> Option<MemberRecord> {
        if position < self.node_count as usize {
            Some(self.members[position])
        } else {
            None
        }
    }

    pub fn membership_root(&self) -> Result<[u8; 32], RecoveryError> {
        self.validate()?;
        let mut hasher = Sha256::new();
        hasher.update(b"BOS/MEMBERSHIP/v3");
        hasher.update(self.cluster_id);
        hasher.update(self.epoch.to_be_bytes());
        hasher.update([self.node_count]);
        let mut index = 0usize;
        while index < self.node_count as usize {
            let member = self.members[index];
            hasher.update([member.node_id]);
            hasher.update([u8::from(member.active)]);
            hasher.update(member.verifying_key);
            index += 1;
        }
        Ok(hasher.finalize().into())
    }
}

#[derive(Clone, Copy)]
pub struct QuorumVerifier {
    policy: ConsensusPolicy,
    manifest: MembershipManifest,
}

impl QuorumVerifier {
    pub fn new(
        policy: ConsensusPolicy,
        manifest: MembershipManifest,
    ) -> Result<Self, RecoveryError> {
        manifest.validate()?;
        if policy.n_nodes() != manifest.node_count() {
            return Err(RecoveryError::QuorumPolicyInvalid);
        }
        Ok(Self { policy, manifest })
    }

    pub const fn policy(&self) -> ConsensusPolicy {
        self.policy
    }

    pub const fn manifest(&self) -> &MembershipManifest {
        &self.manifest
    }

    pub fn verify_certificate(&self, capsule: &StateCapsuleV3) -> Result<(), RecoveryError> {
        if capsule.cluster_id != self.manifest.cluster_id() {
            return Err(RecoveryError::ClusterMismatch);
        }
        if capsule.membership_epoch != self.manifest.epoch() {
            return Err(RecoveryError::MembershipEpochMismatch);
        }
        let expected_membership_root = self.manifest.membership_root()?;
        if capsule.certificate.membership_root() != expected_membership_root {
            return Err(RecoveryError::MembershipRootMismatch);
        }

        let node_count = self.policy.n_nodes() as usize;
        let allowed_mask = (1u16 << node_count) - 1;
        let signer_bitmap = capsule.certificate.signer_bitmap();
        if signer_bitmap & !allowed_mask != 0 {
            return Err(RecoveryError::SignerOutsideMembership);
        }

        let proposal_digest = capsule.proposal_digest()?;
        let mut valid = 0u8;
        let mut position = 0usize;
        while position < MAX_QUORUM_NODES {
            let signature_bytes = capsule
                .certificate
                .signature_at(position)
                .ok_or(RecoveryError::SignerOutsideMembership)?;
            let selected = signer_bitmap & (1u16 << position) != 0;
            if position >= node_count {
                if selected || *signature_bytes != [0u8; 64] {
                    return Err(RecoveryError::SignerOutsideMembership);
                }
                position += 1;
                continue;
            }

            if !selected {
                if *signature_bytes != [0u8; 64] {
                    return Err(RecoveryError::UnexpectedSignatureBytes);
                }
                position += 1;
                continue;
            }

            let member = self
                .manifest
                .member_at(position)
                .ok_or(RecoveryError::SignerOutsideMembership)?;
            if !member.active {
                return Err(RecoveryError::SignerOutsideMembership);
            }
            let key = VerifyingKey::from_bytes(&member.verifying_key)
                .map_err(|_| RecoveryError::InvalidPublicKey)?;
            if key.is_weak() {
                return Err(RecoveryError::InvalidPublicKey);
            }
            let signature = Signature::from_bytes(signature_bytes);
            key.verify_strict(&proposal_digest, &signature)
                .map_err(|_| RecoveryError::InvalidSignature)?;
            valid = valid
                .checked_add(1)
                .ok_or(RecoveryError::ArithmeticOverflow)?;
            position += 1;
        }

        if valid < self.policy.k_threshold() {
            return Err(RecoveryError::QuorumNotMet);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;

    #[test]
    fn rejects_non_intersecting_quorum_policies() {
        assert_eq!(
            ConsensusPolicy::new(4, 2, FaultModel::Crash).err(),
            Some(RecoveryError::QuorumPolicyInvalid)
        );
        assert_eq!(
            ConsensusPolicy::new(9, 5, FaultModel::Byzantine { max_faults: 2 }).err(),
            Some(RecoveryError::QuorumPolicyInvalid)
        );
        assert!(ConsensusPolicy::new(9, 6, FaultModel::Byzantine { max_faults: 2 }).is_ok());
    }

    #[test]
    fn manifest_rejects_duplicate_keys() {
        let key = SigningKey::from_bytes(&[1u8; 32])
            .verifying_key()
            .to_bytes();
        let mut members = [MemberRecord::EMPTY; MAX_QUORUM_NODES];
        members[0] = MemberRecord {
            node_id: 1,
            active: true,
            verifying_key: key,
        };
        members[1] = MemberRecord {
            node_id: 2,
            active: true,
            verifying_key: key,
        };
        assert_eq!(
            MembershipManifest::new([1u8; 16], 1, 2, members).err(),
            Some(RecoveryError::DuplicatePublicKey)
        );
    }
}
