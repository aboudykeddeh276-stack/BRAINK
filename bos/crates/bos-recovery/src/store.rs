use crate::{RecoveryError, StateCapsuleV3, VerifiedCapsule};

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RootSlot {
    A = 1,
    B = 2,
}

impl RootSlot {
    pub const fn inactive(self) -> Self {
        match self {
            Self::A => Self::B,
            Self::B => Self::A,
        }
    }

    pub const fn from_u8(value: u8) -> Option<Self> {
        match value {
            1 => Some(Self::A),
            2 => Some(Self::B),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AnchorState {
    pub cluster_id: [u8; 16],
    pub volume_id: [u8; 16],
    pub membership_epoch: u64,
    pub sequence: u64,
    pub capsule_hash: [u8; 32],
    pub state_root: [u8; 32],
}

impl AnchorState {
    pub const fn genesis(cluster_id: [u8; 16], volume_id: [u8; 16], membership_epoch: u64) -> Self {
        Self {
            cluster_id,
            volume_id,
            membership_epoch,
            sequence: 0,
            capsule_hash: [0u8; 32],
            state_root: [0u8; 32],
        }
    }
}

/// Trusted durable A/B root store.
///
/// Implementations must not report a flush as successful until the target
/// medium has acknowledged the corresponding durability boundary.
pub trait DurableRootStore {
    fn active_slot(&self) -> Result<RootSlot, RecoveryError>;

    fn write_prepared(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
        capsule: &StateCapsuleV3,
    ) -> Result<(), RecoveryError>;

    fn flush_root_slot(&mut self, slot: RootSlot) -> Result<(), RecoveryError>;

    fn publish_selector(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
    ) -> Result<(), RecoveryError>;

    fn flush_selector(&mut self) -> Result<(), RecoveryError>;
}

/// Hardgate anti-rollback authority.
///
/// A production implementation is expected to bind this transition to a TPM,
/// secure element, monotonic counter, or equivalent non-exportable authority.
pub trait HardgateAnchor {
    fn current(&self) -> Result<AnchorState, RecoveryError>;

    fn advance(
        &mut self,
        expected: &AnchorState,
        next: &VerifiedCapsule,
    ) -> Result<(), RecoveryError>;
}
