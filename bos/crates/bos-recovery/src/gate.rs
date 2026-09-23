use core::sync::atomic::{AtomicU8, Ordering};

use bos_cap::{CapHandle, CapTable};

use crate::{
    AnchorState, CapabilityBoundBlockIo, DurableRootStore, HardgateAnchor, QuorumVerifier,
    RecoveryError, RecoveryRequest, RootSlot, StateCapsuleV3, compute_geometry_bound_merkle_root,
    derive_extent_map_root, derive_state_root,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CommitReceipt {
    pub capsule_hash: [u8; 32],
    pub state_root: [u8; 32],
    pub sequence: u64,
    pub membership_epoch: u64,
    pub active_slot: RootSlot,
}

/// Authority-bearing capsule token.
///
/// Fields are private and the only constructor is inside the complete recovery
/// verification path.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct VerifiedCapsule {
    capsule_hash: [u8; 32],
    state_root: [u8; 32],
    sequence: u64,
    membership_epoch: u64,
    cluster_id: [u8; 16],
    volume_id: [u8; 16],
    parent_capsule_hash: [u8; 32],
    parent_state_root: [u8; 32],
}

impl VerifiedCapsule {
    pub const fn capsule_hash(&self) -> [u8; 32] {
        self.capsule_hash
    }

    pub const fn state_root(&self) -> [u8; 32] {
        self.state_root
    }

    pub const fn sequence(&self) -> u64 {
        self.sequence
    }

    pub const fn membership_epoch(&self) -> u64 {
        self.membership_epoch
    }

    pub const fn cluster_id(&self) -> [u8; 16] {
        self.cluster_id
    }

    pub const fn volume_id(&self) -> [u8; 16] {
        self.volume_id
    }

    pub const fn parent_capsule_hash(&self) -> [u8; 32] {
        self.parent_capsule_hash
    }

    pub const fn parent_state_root(&self) -> [u8; 32] {
        self.parent_state_root
    }
}

pub struct HardenedRecoveryEngine {
    active_slot: AtomicU8,
    quorum: QuorumVerifier,
}

impl HardenedRecoveryEngine {
    pub fn new(
        initial_active_slot: RootSlot,
        quorum: QuorumVerifier,
    ) -> Result<Self, RecoveryError> {
        quorum.manifest().validate()?;
        Ok(Self {
            active_slot: AtomicU8::new(initial_active_slot as u8),
            quorum,
        })
    }

    pub fn active_slot(&self) -> RootSlot {
        RootSlot::from_u8(self.active_slot.load(Ordering::Acquire)).unwrap_or(RootSlot::A)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn recover_and_commit<IO, STORE, ANCHOR>(
        &self,
        cap_table: &CapTable,
        storage_handle: CapHandle,
        request: &RecoveryRequest,
        capsule: &StateCapsuleV3,
        io: &mut IO,
        store: &mut STORE,
        anchor: &mut ANCHOR,
    ) -> Result<CommitReceipt, RecoveryError>
    where
        IO: CapabilityBoundBlockIo,
        STORE: DurableRootStore,
        ANCHOR: HardgateAnchor,
    {
        request.validate()?;
        let anchor_before = anchor.current()?;
        self.verify_static_authority(request, capsule, &anchor_before)?;

        // INV-REC-01: no raw read is issued before a generation-pinned extent
        // lease has been established by the authoritative capability table.
        let lease = cap_table.bind_read_extent(
            storage_handle,
            request.start_lba,
            request.lba_count,
            request.logical_block_size,
        )?;

        let extent_descriptor = {
            let read = io.read_exact(&lease, request)?;
            read.receipt().verify(&lease, request)?;
            if read.blocks().len() != request.block_count()? {
                return Err(RecoveryError::ReadGeometryMismatch);
            }

            let computed_data_root = compute_geometry_bound_merkle_root(request, read.blocks())?;
            if computed_data_root != capsule.data_merkle_root {
                return Err(RecoveryError::MerkleMismatch);
            }

            read.receipt().descriptor()
        };
        let computed_extent_root = derive_extent_map_root(&extent_descriptor);
        if computed_extent_root != capsule.extent_map_root {
            return Err(RecoveryError::ExtentRootMismatch);
        }

        if derive_state_root(capsule) != capsule.state_root {
            return Err(RecoveryError::StateRootMismatch);
        }
        self.quorum.verify_certificate(capsule)?;

        let verified = VerifiedCapsule {
            capsule_hash: capsule.capsule_hash()?,
            state_root: capsule.state_root,
            sequence: capsule.capsule_sequence,
            membership_epoch: capsule.membership_epoch,
            cluster_id: capsule.cluster_id,
            volume_id: capsule.volume_id,
            parent_capsule_hash: capsule.parent_capsule_hash,
            parent_state_root: capsule.parent_state_root,
        };

        // INV-REC-03: the inactive slot is made durable before the Hardgate
        // anti-rollback anchor advances. The selector is published last.
        let persisted_active = store.active_slot()?;
        let inactive = persisted_active.inactive();
        store.write_prepared(inactive, &verified, capsule)?;
        store.flush_root_slot(inactive)?;
        anchor.advance(&anchor_before, &verified)?;
        store.publish_selector(inactive, &verified)?;
        store.flush_selector()?;

        self.active_slot.store(inactive as u8, Ordering::Release);
        Ok(CommitReceipt {
            capsule_hash: verified.capsule_hash,
            state_root: verified.state_root,
            sequence: verified.sequence,
            membership_epoch: verified.membership_epoch,
            active_slot: inactive,
        })
    }

    fn verify_static_authority(
        &self,
        request: &RecoveryRequest,
        capsule: &StateCapsuleV3,
        anchor: &AnchorState,
    ) -> Result<(), RecoveryError> {
        if capsule.cluster_id != request.cluster_id || capsule.cluster_id != anchor.cluster_id {
            return Err(RecoveryError::ClusterMismatch);
        }
        if capsule.volume_id != request.volume_id || capsule.volume_id != anchor.volume_id {
            return Err(RecoveryError::VolumeMismatch);
        }
        if capsule.membership_epoch != anchor.membership_epoch
            || capsule.membership_epoch != self.quorum.manifest().epoch()
        {
            return Err(RecoveryError::MembershipEpochMismatch);
        }
        if capsule.capsule_sequence <= anchor.sequence {
            return Err(RecoveryError::StaleSequence);
        }
        if capsule.parent_capsule_hash != anchor.capsule_hash {
            return Err(RecoveryError::ParentCapsuleMismatch);
        }
        if capsule.parent_state_root != anchor.state_root {
            return Err(RecoveryError::ParentStateMismatch);
        }
        if capsule.start_lba != request.start_lba
            || capsule.logical_block_count != request.lba_count
            || capsule.logical_block_size != request.logical_block_size
            || capsule.total_state_bytes != request.total_bytes()?
        {
            return Err(RecoveryError::CapsuleGeometryMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use bos_cap::{CapRecord, CapTable, ResourceKind, rights};
    use ed25519_dalek::{Signer, SigningKey};
    use sha2::{Digest, Sha256};

    use super::*;
    use crate::{
        CommitCertificate, ConsensusPolicy, FaultModel, MAX_QUORUM_NODES, MAX_RECOVERY_BLOCKS,
        MemberRecord, MembershipManifest, RecoveryBlock, derive_extent_map_root,
        simulation::{MemoryBlockIo, MemoryHardgateAnchor, MemoryRootStore},
    };

    const CLUSTER: [u8; 16] = [0x11; 16];
    const VOLUME: [u8; 16] = [0x22; 16];

    fn hash(label: &[u8]) -> [u8; 32] {
        Sha256::digest(label).into()
    }

    struct Fixture {
        table: CapTable,
        handle: CapHandle,
        request: RecoveryRequest,
        io: MemoryBlockIo,
        quorum: QuorumVerifier,
        keys: [SigningKey; 4],
        anchor_state: AnchorState,
    }

    fn fixture() -> Fixture {
        let keys = [
            SigningKey::from_bytes(&[1u8; 32]),
            SigningKey::from_bytes(&[2u8; 32]),
            SigningKey::from_bytes(&[3u8; 32]),
            SigningKey::from_bytes(&[4u8; 32]),
        ];
        let mut members = [MemberRecord::EMPTY; MAX_QUORUM_NODES];
        let mut index = 0usize;
        while index < keys.len() {
            members[index] = MemberRecord {
                node_id: (index + 1) as u8,
                active: true,
                verifying_key: keys[index].verifying_key().to_bytes(),
            };
            index += 1;
        }
        let manifest = MembershipManifest::new(CLUSTER, 1, 4, members).unwrap();
        let policy = ConsensusPolicy::new(4, 3, FaultModel::Crash).unwrap();
        let quorum = QuorumVerifier::new(policy, manifest).unwrap();

        let mut table = CapTable::new();
        let record = CapRecord::new_extent(
            ResourceKind::NvmeNamespaceExtent,
            rights::READ,
            100,
            64,
            7,
            4096,
            1,
        )
        .unwrap();
        let handle = table.install_at(0, record).unwrap();
        let request = RecoveryRequest {
            cluster_id: CLUSTER,
            volume_id: VOLUME,
            start_lba: 100,
            lba_count: 3,
            logical_block_size: 4096,
        };

        let mut blocks = [RecoveryBlock::ZERO; MAX_RECOVERY_BLOCKS];
        let mut block_index = 0usize;
        while block_index < 3 {
            let fill = (block_index as u8) + 1;
            blocks[block_index].as_mut_bytes().fill(fill);
            block_index += 1;
        }
        let io = MemoryBlockIo::new(blocks, 3, [0xA5; 32], 7).unwrap();
        let anchor_state = AnchorState::genesis(CLUSTER, VOLUME, 1);

        Fixture {
            table,
            handle,
            request,
            io,
            quorum,
            keys,
            anchor_state,
        }
    }

    fn signed_capsule(fixture: &Fixture) -> StateCapsuleV3 {
        let data_root =
            compute_geometry_bound_merkle_root(&fixture.request, fixture.io.blocks()).unwrap();
        let descriptor = fixture.io.descriptor_for(fixture.handle, &fixture.request);
        let membership_root = fixture.quorum.manifest().membership_root().unwrap();
        let certificate = CommitCertificate::new(membership_root);
        let mut capsule = StateCapsuleV3 {
            cluster_id: CLUSTER,
            volume_id: VOLUME,
            membership_epoch: 1,
            consensus_view: 1,
            capsule_sequence: 1,
            parent_capsule_hash: fixture.anchor_state.capsule_hash,
            parent_state_root: fixture.anchor_state.state_root,
            data_merkle_root: data_root,
            manifest_root: hash(b"BOS demo state manifest"),
            extent_map_root: derive_extent_map_root(&descriptor),
            state_root: [0u8; 32],
            start_lba: fixture.request.start_lba,
            logical_block_count: fixture.request.lba_count,
            logical_block_size: fixture.request.logical_block_size,
            total_state_bytes: fixture.request.total_bytes().unwrap(),
            certificate,
        };
        capsule.state_root = derive_state_root(&capsule);
        let digest = capsule.proposal_digest().unwrap();
        let mut position = 0usize;
        while position < 3 {
            capsule
                .certificate
                .set_signature(position, fixture.keys[position].sign(&digest).to_bytes())
                .unwrap();
            position += 1;
        }
        capsule
    }

    #[test]
    fn complete_recovery_commits_inactive_slot_and_advances_anchor() {
        let mut fixture = fixture();
        let capsule = signed_capsule(&fixture);
        let engine = HardenedRecoveryEngine::new(RootSlot::A, fixture.quorum).unwrap();
        let mut store = MemoryRootStore::new(RootSlot::A);
        let mut anchor = MemoryHardgateAnchor::new(fixture.anchor_state);

        let receipt = engine
            .recover_and_commit(
                &fixture.table,
                fixture.handle,
                &fixture.request,
                &capsule,
                &mut fixture.io,
                &mut store,
                &mut anchor,
            )
            .unwrap();

        assert_eq!(receipt.active_slot, RootSlot::B);
        assert_eq!(receipt.sequence, 1);
        assert_eq!(engine.active_slot(), RootSlot::B);
        assert_eq!(store.active_slot().unwrap(), RootSlot::B);
        assert_eq!(store.selector_sequence(), 1);
        assert_eq!(anchor.current().unwrap().capsule_hash, receipt.capsule_hash);
    }

    #[test]
    fn stale_capsule_and_short_read_fail_closed() {
        let mut stale_fixture = fixture();
        let mut capsule = signed_capsule(&stale_fixture);
        let engine = HardenedRecoveryEngine::new(RootSlot::A, stale_fixture.quorum).unwrap();
        let mut store = MemoryRootStore::new(RootSlot::A);
        let mut stale_anchor = stale_fixture.anchor_state;
        stale_anchor.sequence = 1;
        let mut anchor = MemoryHardgateAnchor::new(stale_anchor);
        assert_eq!(
            engine
                .recover_and_commit(
                    &stale_fixture.table,
                    stale_fixture.handle,
                    &stale_fixture.request,
                    &capsule,
                    &mut stale_fixture.io,
                    &mut store,
                    &mut anchor,
                )
                .err(),
            Some(RecoveryError::StaleSequence)
        );

        let mut short_read_fixture = fixture();
        capsule = signed_capsule(&short_read_fixture);
        short_read_fixture
            .io
            .set_completed_bytes_override(Some(4096));
        let mut store = MemoryRootStore::new(RootSlot::A);
        let mut anchor = MemoryHardgateAnchor::new(short_read_fixture.anchor_state);
        assert_eq!(
            engine
                .recover_and_commit(
                    &short_read_fixture.table,
                    short_read_fixture.handle,
                    &short_read_fixture.request,
                    &capsule,
                    &mut short_read_fixture.io,
                    &mut store,
                    &mut anchor,
                )
                .err(),
            Some(RecoveryError::ShortRead)
        );
        assert_eq!(store.active_slot().unwrap(), RootSlot::A);
    }

    #[test]
    fn leaf_count_is_committed_even_when_last_leaf_is_duplicated() {
        let fixture = fixture();
        let root_three =
            compute_geometry_bound_merkle_root(&fixture.request, fixture.io.blocks()).unwrap();

        let mut request_four = fixture.request;
        request_four.lba_count = 4;
        let mut blocks = [RecoveryBlock::ZERO; MAX_RECOVERY_BLOCKS];
        blocks[..3].copy_from_slice(fixture.io.blocks());
        blocks[3] = blocks[2];
        let root_four = compute_geometry_bound_merkle_root(&request_four, &blocks[..4]).unwrap();
        assert_ne!(root_three, root_four);
    }
}
