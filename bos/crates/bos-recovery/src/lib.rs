#![cfg_attr(not(any(test, feature = "std")), no_std)]
#![deny(unsafe_op_in_unsafe_fn)]

//! Authenticated BOS cold recovery.
//!
//! The safe API has no operation that publishes a raw [`StateCapsuleV3`].
//! Publication requires a private [`VerifiedCapsule`] produced by the complete
//! capability, hardware-receipt, Merkle, quorum, freshness, and state-root
//! verification path.
//!
//! ```compile_fail
//! use bos_recovery::VerifiedCapsule;
//!
//! // Fields are private: an untrusted caller cannot manufacture authority.
//! let _forged = VerifiedCapsule {
//!     capsule_hash: [0; 32],
//!     state_root: [0; 32],
//!     sequence: 1,
//!     membership_epoch: 1,
//! };
//! ```

mod capsule;
mod error;
mod gate;
mod io;
mod merkle;
mod quorum;
mod request;
mod store;

#[cfg(any(test, feature = "std"))]
pub mod simulation;

pub use capsule::{CAPSULE_ENCODED_LEN, CommitCertificate, StateCapsuleV3, derive_state_root};
pub use error::RecoveryError;
pub use gate::{CommitReceipt, HardenedRecoveryEngine, VerifiedCapsule};
pub use io::{
    CapabilityBoundBlockIo, ExtentDescriptor, ReadBatch, ReadReceipt, RecoveryBlock,
    derive_extent_map_root,
};
pub use merkle::compute_geometry_bound_merkle_root;
pub use quorum::{ConsensusPolicy, FaultModel, MemberRecord, MembershipManifest, QuorumVerifier};
pub use request::{MAX_QUORUM_NODES, MAX_RECOVERY_BLOCKS, RECOVERY_BLOCK_BYTES, RecoveryRequest};
pub use store::{AnchorState, DurableRootStore, HardgateAnchor, RootSlot};
