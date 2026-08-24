#![no_std]
#![forbid(unsafe_code)]

//! Minimal fixed-capacity capability substrate for BOS recovery.
//!
//! The capability table is authoritative. Application-visible handles carry a
//! slot and generation, while an [`ExtentLease`] pins an immutable capability
//! record for the duration of a hardware operation. Safe Rust cannot mutate or
//! replace the table while such a lease is alive.

pub const MAX_CAPABILITIES: usize = 64;

pub mod rights {
    pub const READ: u64 = 1 << 0;
    pub const WRITE: u64 = 1 << 1;
    pub const MAP: u64 = 1 << 2;
    pub const DMA: u64 = 1 << 3;
    pub const BIND: u64 = 1 << 4;
    pub const SUBMIT: u64 = 1 << 5;
    pub const DELEGATE: u64 = 1 << 6;
    pub const REVOKE: u64 = 1 << 7;
    pub const RESET: u64 = 1 << 8;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CapError {
    TableFull,
    InvalidSlot,
    InvalidGeneration,
    InvalidExtent,
    InvalidGeometry,
    Inactive,
    StaleHandle,
    AccessDenied,
    WrongResourceKind,
    ExtentOutOfBounds,
    ArithmeticOverflow,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CapHandle {
    slot: u16,
    generation: u64,
}

impl CapHandle {
    pub const fn new(slot: u16, generation: u64) -> Result<Self, CapError> {
        if generation == 0 {
            return Err(CapError::InvalidGeneration);
        }
        Ok(Self { slot, generation })
    }

    pub const fn slot(self) -> u16 {
        self.slot
    }

    pub const fn generation(self) -> u64 {
        self.generation
    }
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ResourceKind {
    DiskBlockExtent = 1,
    NvmeNamespaceExtent = 2,
    DmaPageSet = 3,
    NvmeSubmissionQueue = 4,
    NvmeCompletionQueue = 5,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CapRecord {
    resource_kind: ResourceKind,
    rights: u64,
    extent_start: u64,
    extent_len: u64,
    namespace_id: u32,
    logical_block_size: u32,
    generation: u64,
    active: bool,
}

impl CapRecord {
    #[allow(clippy::too_many_arguments)]
    pub const fn new_extent(
        resource_kind: ResourceKind,
        rights: u64,
        extent_start: u64,
        extent_len: u64,
        namespace_id: u32,
        logical_block_size: u32,
        generation: u64,
    ) -> Result<Self, CapError> {
        if !matches!(
            resource_kind,
            ResourceKind::DiskBlockExtent | ResourceKind::NvmeNamespaceExtent
        ) {
            return Err(CapError::WrongResourceKind);
        }
        if extent_len == 0 {
            return Err(CapError::InvalidExtent);
        }
        if logical_block_size == 0 || generation == 0 {
            return Err(if logical_block_size == 0 {
                CapError::InvalidGeometry
            } else {
                CapError::InvalidGeneration
            });
        }
        if extent_start.checked_add(extent_len).is_none() {
            return Err(CapError::ArithmeticOverflow);
        }

        Ok(Self {
            resource_kind,
            rights,
            extent_start,
            extent_len,
            namespace_id,
            logical_block_size,
            generation,
            active: true,
        })
    }

    pub const fn resource_kind(self) -> ResourceKind {
        self.resource_kind
    }

    pub const fn rights(self) -> u64 {
        self.rights
    }

    pub const fn extent_start(self) -> u64 {
        self.extent_start
    }

    pub const fn extent_len(self) -> u64 {
        self.extent_len
    }

    pub const fn namespace_id(self) -> u32 {
        self.namespace_id
    }

    pub const fn logical_block_size(self) -> u32 {
        self.logical_block_size
    }

    pub const fn generation(self) -> u64 {
        self.generation
    }

    pub const fn is_active(self) -> bool {
        self.active
    }

    pub const fn with_active(mut self, active: bool) -> Self {
        self.active = active;
        self
    }
}

pub struct CapTable {
    records: [Option<CapRecord>; MAX_CAPABILITIES],
}

impl CapTable {
    pub const fn new() -> Self {
        Self {
            records: [None; MAX_CAPABILITIES],
        }
    }

    pub fn install_at(&mut self, slot: u16, record: CapRecord) -> Result<CapHandle, CapError> {
        let index = usize::from(slot);
        if index >= MAX_CAPABILITIES {
            return Err(CapError::InvalidSlot);
        }
        self.records[index] = Some(record);
        CapHandle::new(slot, record.generation())
    }

    pub fn install_first_free(&mut self, record: CapRecord) -> Result<CapHandle, CapError> {
        let mut index = 0usize;
        while index < MAX_CAPABILITIES {
            if self.records[index].is_none() {
                self.records[index] = Some(record);
                return CapHandle::new(index as u16, record.generation());
            }
            index += 1;
        }
        Err(CapError::TableFull)
    }

    pub fn revoke(&mut self, handle: CapHandle) -> Result<(), CapError> {
        let record = self.get_active(handle)?;
        self.records[usize::from(handle.slot())] = Some(record.with_active(false));
        Ok(())
    }

    pub fn replace(
        &mut self,
        old_handle: CapHandle,
        replacement: CapRecord,
    ) -> Result<CapHandle, CapError> {
        let _ = self.get_active(old_handle)?;
        if replacement.generation() <= old_handle.generation() {
            return Err(CapError::InvalidGeneration);
        }
        self.install_at(old_handle.slot(), replacement)
    }

    pub fn get_active(&self, handle: CapHandle) -> Result<CapRecord, CapError> {
        let index = usize::from(handle.slot());
        let record = self
            .records
            .get(index)
            .copied()
            .flatten()
            .ok_or(CapError::InvalidSlot)?;
        if !record.is_active() {
            return Err(CapError::Inactive);
        }
        if record.generation() != handle.generation() {
            return Err(CapError::StaleHandle);
        }
        Ok(record)
    }

    pub fn bind_read_extent(
        &self,
        handle: CapHandle,
        start_lba: u64,
        lba_count: u64,
        logical_block_size: u32,
    ) -> Result<ExtentLease<'_>, CapError> {
        if lba_count == 0 {
            return Err(CapError::InvalidExtent);
        }
        let record = self.get_active(handle)?;
        if !matches!(
            record.resource_kind(),
            ResourceKind::DiskBlockExtent | ResourceKind::NvmeNamespaceExtent
        ) {
            return Err(CapError::WrongResourceKind);
        }
        if record.rights() & rights::READ == 0 {
            return Err(CapError::AccessDenied);
        }
        if record.logical_block_size() != logical_block_size {
            return Err(CapError::InvalidGeometry);
        }

        let requested_end = start_lba
            .checked_add(lba_count)
            .ok_or(CapError::ArithmeticOverflow)?;
        let capability_end = record
            .extent_start()
            .checked_add(record.extent_len())
            .ok_or(CapError::ArithmeticOverflow)?;
        if start_lba < record.extent_start() || requested_end > capability_end {
            return Err(CapError::ExtentOutOfBounds);
        }

        Ok(ExtentLease {
            _table: self,
            handle,
            record,
            start_lba,
            lba_count,
        })
    }
}

impl Default for CapTable {
    fn default() -> Self {
        Self::new()
    }
}

/// Immutable generation-pinned authorization for one exact read range.
///
/// The private borrow of the table ensures that safe code cannot replace or
/// revoke the underlying record before the lease is dropped.
pub struct ExtentLease<'a> {
    _table: &'a CapTable,
    handle: CapHandle,
    record: CapRecord,
    start_lba: u64,
    lba_count: u64,
}

impl ExtentLease<'_> {
    pub const fn handle(&self) -> CapHandle {
        self.handle
    }

    pub const fn resource_kind(&self) -> ResourceKind {
        self.record.resource_kind()
    }

    pub const fn rights(&self) -> u64 {
        self.record.rights()
    }

    pub const fn namespace_id(&self) -> u32 {
        self.record.namespace_id()
    }

    pub const fn logical_block_size(&self) -> u32 {
        self.record.logical_block_size()
    }

    pub const fn start_lba(&self) -> u64 {
        self.start_lba
    }

    pub const fn lba_count(&self) -> u64 {
        self.lba_count
    }

    pub const fn capability_extent_start(&self) -> u64 {
        self.record.extent_start()
    }

    pub const fn capability_extent_len(&self) -> u64 {
        self.record.extent_len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_stale_generation_and_out_of_range_access() {
        let mut table = CapTable::new();
        let record = CapRecord::new_extent(
            ResourceKind::NvmeNamespaceExtent,
            rights::READ,
            100,
            16,
            7,
            4096,
            1,
        )
        .unwrap();
        let handle = table.install_at(0, record).unwrap();

        assert!(table.bind_read_extent(handle, 100, 16, 4096).is_ok());
        assert_eq!(
            table.bind_read_extent(handle, 99, 1, 4096).err(),
            Some(CapError::ExtentOutOfBounds)
        );

        let replacement = CapRecord::new_extent(
            ResourceKind::NvmeNamespaceExtent,
            rights::READ,
            100,
            16,
            7,
            4096,
            2,
        )
        .unwrap();
        let new_handle = table.replace(handle, replacement).unwrap();
        assert_eq!(table.get_active(handle).err(), Some(CapError::StaleHandle));
        assert!(table.get_active(new_handle).is_ok());
    }
}
