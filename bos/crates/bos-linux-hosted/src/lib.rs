//! Linux-hosted adapters for the BOS recovery contract.
//!
//! `IoUringReadBackend` is a Linux transition backend. It is not represented as
//! the native BOS NVMe queue implementation.

#[cfg(target_os = "linux")]
mod linux;

#[cfg(target_os = "linux")]
pub use linux::{FileAbRootStore, IoUringReadBackend};

#[cfg(not(target_os = "linux"))]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UnsupportedPlatform;
