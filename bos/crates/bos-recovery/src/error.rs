use bos_cap::CapError;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RecoveryError {
    Capability(CapError),
    InvalidRequest,
    EmptyRange,
    ArithmeticOverflow,
    TooManyBlocks,
    ReadBindingMismatch,
    ReadGeometryMismatch,
    ShortRead,
    BackendIo(i32),
    BackendUnavailable,
    MerkleMismatch,
    InvalidCapsuleLength,
    InvalidCapsuleMagic,
    UnsupportedCapsuleVersion,
    UnsupportedHashAlgorithm,
    UnsupportedSignatureAlgorithm,
    NonCanonicalEncoding,
    CapsuleGeometryMismatch,
    ClusterMismatch,
    VolumeMismatch,
    MembershipEpochMismatch,
    MembershipRootMismatch,
    InvalidMembership,
    DuplicateNodeId,
    DuplicatePublicKey,
    InvalidNodeId,
    InvalidPublicKey,
    InvalidSignature,
    QuorumPolicyInvalid,
    QuorumNotMet,
    SignerOutsideMembership,
    UnexpectedSignatureBytes,
    StateRootMismatch,
    ExtentRootMismatch,
    StaleSequence,
    ParentCapsuleMismatch,
    ParentStateMismatch,
    AnchorConflict,
    RootStoreFailure,
    SelectorFailure,
}

impl From<CapError> for RecoveryError {
    fn from(value: CapError) -> Self {
        Self::Capability(value)
    }
}
