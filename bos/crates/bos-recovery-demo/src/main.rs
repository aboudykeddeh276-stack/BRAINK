use bos_cap::{CapRecord, CapTable, ResourceKind, rights};
use bos_recovery::{
    AnchorState, CommitCertificate, ConsensusPolicy, FaultModel, HardenedRecoveryEngine,
    MAX_QUORUM_NODES, MAX_RECOVERY_BLOCKS, MemberRecord, MembershipManifest, QuorumVerifier,
    RecoveryBlock, RecoveryRequest, RootSlot, StateCapsuleV3, compute_geometry_bound_merkle_root,
    derive_extent_map_root, derive_state_root,
    simulation::{MemoryBlockIo, MemoryHardgateAnchor, MemoryRootStore},
};
use ed25519_dalek::{Signer, SigningKey};
use sha2::{Digest, Sha256};

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(DIGITS[(byte >> 4) as usize] as char);
        output.push(DIGITS[(byte & 0x0f) as usize] as char);
    }
    output
}

fn main() -> Result<(), String> {
    let cluster_id = [0x31u8; 16];
    let volume_id = [0x41u8; 16];
    let keys = [
        SigningKey::from_bytes(&[1u8; 32]),
        SigningKey::from_bytes(&[2u8; 32]),
        SigningKey::from_bytes(&[3u8; 32]),
        SigningKey::from_bytes(&[4u8; 32]),
    ];

    let mut members = [MemberRecord::EMPTY; MAX_QUORUM_NODES];
    for (position, key) in keys.iter().enumerate() {
        members[position] = MemberRecord {
            node_id: (position + 1) as u8,
            active: true,
            verifying_key: key.verifying_key().to_bytes(),
        };
    }
    let manifest = MembershipManifest::new(cluster_id, 1, 4, members)
        .map_err(|error| format!("membership: {error:?}"))?;
    let policy = ConsensusPolicy::new(4, 3, FaultModel::Crash)
        .map_err(|error| format!("policy: {error:?}"))?;
    let quorum =
        QuorumVerifier::new(policy, manifest).map_err(|error| format!("quorum: {error:?}"))?;

    let mut cap_table = CapTable::new();
    let record = CapRecord::new_extent(
        ResourceKind::NvmeNamespaceExtent,
        rights::READ,
        1,
        32,
        1,
        4096,
        1,
    )
    .map_err(|error| format!("capability record: {error:?}"))?;
    let storage_handle = cap_table
        .install_at(0, record)
        .map_err(|error| format!("capability install: {error:?}"))?;

    let request = RecoveryRequest {
        cluster_id,
        volume_id,
        start_lba: 1,
        lba_count: 3,
        logical_block_size: 4096,
    };
    let mut blocks = [RecoveryBlock::ZERO; MAX_RECOVERY_BLOCKS];
    for (index, block) in blocks[..3].iter_mut().enumerate() {
        block.as_mut_bytes().fill((index + 1) as u8);
    }
    let mut io = MemoryBlockIo::new(blocks, 3, [0xAB; 32], 1)
        .map_err(|error| format!("memory I/O: {error:?}"))?;

    let data_root = compute_geometry_bound_merkle_root(&request, io.blocks())
        .map_err(|error| format!("Merkle root: {error:?}"))?;
    let extent_root = derive_extent_map_root(&io.descriptor_for(storage_handle, &request));
    let membership_root = quorum
        .manifest()
        .membership_root()
        .map_err(|error| format!("membership root: {error:?}"))?;
    let anchor_state = AnchorState::genesis(cluster_id, volume_id, 1);

    let mut capsule = StateCapsuleV3 {
        cluster_id,
        volume_id,
        membership_epoch: 1,
        consensus_view: 1,
        capsule_sequence: 1,
        parent_capsule_hash: anchor_state.capsule_hash,
        parent_state_root: anchor_state.state_root,
        data_merkle_root: data_root,
        manifest_root: Sha256::digest(b"BOS recovery demo manifest").into(),
        extent_map_root: extent_root,
        state_root: [0u8; 32],
        start_lba: request.start_lba,
        logical_block_count: request.lba_count,
        logical_block_size: request.logical_block_size,
        total_state_bytes: request
            .total_bytes()
            .map_err(|error| format!("request bytes: {error:?}"))?,
        certificate: CommitCertificate::new(membership_root),
    };
    capsule.state_root = derive_state_root(&capsule);
    let proposal_digest = capsule
        .proposal_digest()
        .map_err(|error| format!("proposal digest: {error:?}"))?;
    for (position, key) in keys.iter().take(3).enumerate() {
        capsule
            .certificate
            .set_signature(position, key.sign(&proposal_digest).to_bytes())
            .map_err(|error| format!("signature: {error:?}"))?;
    }

    let engine = HardenedRecoveryEngine::new(RootSlot::A, quorum)
        .map_err(|error| format!("engine: {error:?}"))?;
    let mut store = MemoryRootStore::new(RootSlot::A);
    let mut anchor = MemoryHardgateAnchor::new(anchor_state);
    let receipt = engine
        .recover_and_commit(
            &cap_table,
            storage_handle,
            &request,
            &capsule,
            &mut io,
            &mut store,
            &mut anchor,
        )
        .map_err(|error| format!("recovery commit: {error:?}"))?;

    println!(
        "{{\"status\":\"PASS\",\"active_slot\":\"{:?}\",\"sequence\":{},\"capsule_hash\":\"{}\",\"state_root\":\"{}\",\"data_merkle_root\":\"{}\",\"extent_map_root\":\"{}\",\"quorum\":\"3-of-4 crash-fault\"}}",
        receipt.active_slot,
        receipt.sequence,
        hex(&receipt.capsule_hash),
        hex(&receipt.state_root),
        hex(&data_root),
        hex(&extent_root),
    );
    Ok(())
}
