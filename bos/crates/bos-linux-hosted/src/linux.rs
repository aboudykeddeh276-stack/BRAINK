use std::ffi::c_void;
use std::fs::{self, File, OpenOptions};
use std::io;
use std::os::fd::AsRawFd;
use std::os::unix::fs::FileExt;
use std::path::Path;

use bos_cap::ExtentLease;
use bos_recovery::{
    CAPSULE_ENCODED_LEN, CapabilityBoundBlockIo, DurableRootStore, ExtentDescriptor,
    MAX_RECOVERY_BLOCKS, RECOVERY_BLOCK_BYTES, ReadBatch, ReadReceipt, RecoveryBlock,
    RecoveryError, RecoveryRequest, RootSlot, StateCapsuleV3, VerifiedCapsule,
};
use io_uring::{IoUring, opcode, register::Restriction, types};
use sha2::{Digest, Sha256};

const RING_ENTRIES: u32 = 64;
const IORING_REGISTER_ENABLE_RINGS: u8 = 12;
const IOSQE_FIXED_FILE: u8 = 1 << 0;
const READ_TOKEN_PREFIX: u64 = 0xB05C_0100_0000_0000;
const READ_TOKEN_MASK: u64 = 0xFFFF_FF00_0000_0000;
const ROOT_RECORD_MAGIC: [u8; 8] = *b"BOSROOT3";
const SELECTOR_MAGIC: [u8; 8] = *b"BOSSEL3\0";
const ROOT_RECORD_LEN: usize = 8 + 8 + 32 + 32 + 4 + CAPSULE_ENCODED_LEN + 32;
const SELECTOR_RECORD_LEN: usize = 8 + 1 + 7 + 8 + 32 + 32 + 32;
const SELECTOR_COPY_OFFSET: u64 = 4096;

fn map_io(error: io::Error) -> RecoveryError {
    let errno = error.raw_os_error().unwrap_or(libc::EIO);
    RecoveryError::BackendIo(-errno.abs())
}

/// Restricted, fixed-buffer `io_uring` read backend.
///
/// The ring starts disabled. The file and all 32 aligned recovery buffers are
/// registered before a permanent allowlist is installed. The only SQE opcode
/// admitted is `READ_FIXED`; the only registration operation admitted after
/// sealing is the one-time ring enable operation.
pub struct IoUringReadBackend {
    // Field order is intentional: the ring is destroyed before the file and
    // registered backing buffers are dropped.
    ring: IoUring,
    file: File,
    buffers: Box<[RecoveryBlock; MAX_RECOVERY_BLOCKS]>,
    device_identity: [u8; 32],
    namespace_id: u32,
    controller_epoch: u64,
    buffer_generation: u64,
}

impl IoUringReadBackend {
    pub fn new(
        file: File,
        device_identity: [u8; 32],
        namespace_id: u32,
        controller_epoch: u64,
    ) -> Result<Self, RecoveryError> {
        let mut buffers = Box::new([RecoveryBlock::ZERO; MAX_RECOVERY_BLOCKS]);
        let mut builder = IoUring::builder();
        builder.setup_r_disabled().setup_cqsize(RING_ENTRIES * 2);
        let ring = builder.build(RING_ENTRIES).map_err(map_io)?;

        let iovecs: [libc::iovec; MAX_RECOVERY_BLOCKS] =
            core::array::from_fn(|index| libc::iovec {
                iov_base: buffers[index].as_mut_bytes().as_mut_ptr().cast::<c_void>(),
                iov_len: RECOVERY_BLOCK_BYTES,
            });

        // SAFETY: `buffers` is heap allocated and its allocation is not moved.
        // It remains alive until after `ring` is dropped. Every iovec covers one
        // complete aligned RecoveryBlock.
        unsafe {
            ring.submitter().register_buffers(&iovecs).map_err(map_io)?;
        }
        ring.submitter()
            .register_files(&[file.as_raw_fd()])
            .map_err(map_io)?;

        let mut restrictions = [
            Restriction::sqe_op(opcode::ReadFixed::CODE),
            Restriction::sqe_flags_allowed(IOSQE_FIXED_FILE),
            Restriction::register_op(IORING_REGISTER_ENABLE_RINGS),
        ];
        ring.submitter()
            .register_restrictions(&mut restrictions)
            .map_err(map_io)?;
        ring.submitter().register_enable_rings().map_err(map_io)?;

        Ok(Self {
            ring,
            file,
            buffers,
            device_identity,
            namespace_id,
            controller_epoch,
            buffer_generation: 1,
        })
    }

    pub fn file(&self) -> &File {
        &self.file
    }
}

// SAFETY: The backend owns the only ring submission path, uses the exact
// generation-pinned lease to derive its offset, and returns a receipt only after
// collecting and validating every hardware completion.
unsafe impl CapabilityBoundBlockIo for IoUringReadBackend {
    fn read_exact<'a>(
        &'a mut self,
        lease: &ExtentLease<'_>,
        request: &RecoveryRequest,
    ) -> Result<ReadBatch<'a>, RecoveryError> {
        request.validate()?;
        if lease.namespace_id() != self.namespace_id
            || lease.start_lba() != request.start_lba
            || lease.lba_count() != request.lba_count
            || lease.logical_block_size() != request.logical_block_size
        {
            return Err(RecoveryError::ReadBindingMismatch);
        }

        let block_count = request.block_count()?;
        if block_count == 0 || block_count > MAX_RECOVERY_BLOCKS {
            return Err(RecoveryError::TooManyBlocks);
        }
        let base_offset = request
            .start_lba
            .checked_mul(u64::from(request.logical_block_size))
            .ok_or(RecoveryError::ArithmeticOverflow)?;

        let mut expected_lengths = [0usize; MAX_RECOVERY_BLOCKS];
        let mut index = 0usize;
        while index < block_count {
            self.buffers[index].as_mut_bytes().fill(0);
            let length = request.block_len(index)?;
            expected_lengths[index] = length;
            let relative = (index as u64)
                .checked_mul(RECOVERY_BLOCK_BYTES as u64)
                .ok_or(RecoveryError::ArithmeticOverflow)?;
            let offset = base_offset
                .checked_add(relative)
                .ok_or(RecoveryError::ArithmeticOverflow)?;
            let entry = opcode::ReadFixed::new(
                types::Fixed(0),
                self.buffers[index].as_mut_bytes().as_mut_ptr(),
                length as u32,
                index as u16,
            )
            .offset(offset)
            .build()
            .user_data(READ_TOKEN_PREFIX | index as u64);

            // SAFETY: The registered fixed file and buffer index remain valid;
            // the pointer and length are contained within that registered
            // buffer; and the SQE is consumed before either resource can drop.
            unsafe {
                self.ring
                    .submission()
                    .push(&entry)
                    .map_err(|_| RecoveryError::BackendUnavailable)?;
            }
            index += 1;
        }

        self.ring.submit_and_wait(block_count).map_err(map_io)?;

        let mut seen = 0u64;
        let mut completion_count = 0usize;
        let mut completed_bytes = 0u64;
        let mut first_error: Option<RecoveryError> = None;
        {
            let mut completion = self.ring.completion();
            while completion_count < block_count {
                let Some(cqe) = completion.next() else {
                    break;
                };
                let token = cqe.user_data();
                if token & READ_TOKEN_MASK != READ_TOKEN_PREFIX & READ_TOKEN_MASK {
                    first_error.get_or_insert(RecoveryError::ReadBindingMismatch);
                    completion_count += 1;
                    continue;
                }
                let buffer_index = (token & 0xFF) as usize;
                if buffer_index >= block_count || seen & (1u64 << buffer_index) != 0 {
                    first_error.get_or_insert(RecoveryError::ReadBindingMismatch);
                    completion_count += 1;
                    continue;
                }
                seen |= 1u64 << buffer_index;
                let result = cqe.result();
                if result < 0 {
                    first_error.get_or_insert(RecoveryError::BackendIo(result));
                } else if result as usize != expected_lengths[buffer_index] {
                    first_error.get_or_insert(RecoveryError::ShortRead);
                } else {
                    completed_bytes = completed_bytes
                        .checked_add(result as u64)
                        .ok_or(RecoveryError::ArithmeticOverflow)?;
                }
                completion_count += 1;
            }
        }

        if completion_count != block_count || seen.count_ones() as usize != block_count {
            return Err(RecoveryError::ShortRead);
        }
        if let Some(error) = first_error {
            return Err(error);
        }

        let descriptor = ExtentDescriptor {
            capability: lease.handle(),
            device_identity: self.device_identity,
            namespace_id: self.namespace_id,
            start_lba: request.start_lba,
            lba_count: request.lba_count,
            logical_block_size: request.logical_block_size,
        };
        // SAFETY: All fixed-buffer completions were consumed, uniquely matched,
        // and checked for exact byte counts above.
        let receipt = unsafe {
            ReadReceipt::from_trusted_completion(
                descriptor,
                self.controller_epoch,
                self.buffer_generation,
                request.total_bytes()?,
                completed_bytes,
                0,
            )
        };
        // SAFETY: The returned slice is the exact registered buffer set used by
        // those completions and remains immutable for the returned borrow.
        Ok(unsafe { ReadBatch::from_trusted_completion(receipt, &self.buffers[..block_count]) })
    }
}

/// Durable file-backed A/B capsule store for the Linux-hosted transition path.
///
/// The files must live on a filesystem whose `sync_data` implementation reaches
/// the intended durability domain. Production raw-device deployment still
/// requires target-specific flush/FUA receipts.
pub struct FileAbRootStore {
    slot_a: File,
    slot_b: File,
    selector: File,
    active: RootSlot,
    prepared: Option<RootSlot>,
    pending_selector: Option<RootSlot>,
}

impl FileAbRootStore {
    pub fn open(directory: &Path, active: RootSlot) -> Result<Self, RecoveryError> {
        fs::create_dir_all(directory).map_err(map_io)?;
        let slot_a = open_state_file(&directory.join("root-slot-a.bos"))?;
        let slot_b = open_state_file(&directory.join("root-slot-b.bos"))?;
        let selector = open_state_file(&directory.join("root-selector.bos"))?;
        Ok(Self {
            slot_a,
            slot_b,
            selector,
            active,
            prepared: None,
            pending_selector: None,
        })
    }

    fn slot_file(&self, slot: RootSlot) -> &File {
        match slot {
            RootSlot::A => &self.slot_a,
            RootSlot::B => &self.slot_b,
        }
    }
}

impl DurableRootStore for FileAbRootStore {
    fn active_slot(&self) -> Result<RootSlot, RecoveryError> {
        Ok(self.active)
    }

    fn write_prepared(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
        capsule: &StateCapsuleV3,
    ) -> Result<(), RecoveryError> {
        if capsule.capsule_hash()? != verified.capsule_hash()
            || capsule.state_root != verified.state_root()
        {
            return Err(RecoveryError::RootStoreFailure);
        }
        let record = encode_root_record(verified, capsule)?;
        write_all_at(self.slot_file(slot), &record, 0)?;
        self.prepared = Some(slot);
        Ok(())
    }

    fn flush_root_slot(&mut self, slot: RootSlot) -> Result<(), RecoveryError> {
        if self.prepared != Some(slot) {
            return Err(RecoveryError::RootStoreFailure);
        }
        self.slot_file(slot).sync_data().map_err(map_io)
    }

    fn publish_selector(
        &mut self,
        slot: RootSlot,
        verified: &VerifiedCapsule,
    ) -> Result<(), RecoveryError> {
        if self.prepared != Some(slot) {
            return Err(RecoveryError::SelectorFailure);
        }
        let record = encode_selector_record(slot, verified);
        write_all_at(&self.selector, &record, 0)?;
        write_all_at(&self.selector, &record, SELECTOR_COPY_OFFSET)?;
        self.pending_selector = Some(slot);
        Ok(())
    }

    fn flush_selector(&mut self) -> Result<(), RecoveryError> {
        self.selector.sync_data().map_err(map_io)?;
        let slot = self
            .pending_selector
            .take()
            .ok_or(RecoveryError::SelectorFailure)?;
        self.active = slot;
        self.prepared = None;
        Ok(())
    }
}

fn open_state_file(path: &Path) -> Result<File, RecoveryError> {
    OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(map_io)
}

fn write_all_at(file: &File, mut bytes: &[u8], mut offset: u64) -> Result<(), RecoveryError> {
    while !bytes.is_empty() {
        let written = file.write_at(bytes, offset).map_err(map_io)?;
        if written == 0 {
            return Err(RecoveryError::ShortRead);
        }
        offset = offset
            .checked_add(written as u64)
            .ok_or(RecoveryError::ArithmeticOverflow)?;
        bytes = &bytes[written..];
    }
    Ok(())
}

fn encode_root_record(
    verified: &VerifiedCapsule,
    capsule: &StateCapsuleV3,
) -> Result<[u8; ROOT_RECORD_LEN], RecoveryError> {
    let mut capsule_bytes = [0u8; CAPSULE_ENCODED_LEN];
    capsule.encode_into(&mut capsule_bytes)?;
    let mut output = [0u8; ROOT_RECORD_LEN];
    let mut offset = 0usize;
    put(&mut output, &mut offset, &ROOT_RECORD_MAGIC)?;
    put(&mut output, &mut offset, &verified.sequence().to_be_bytes())?;
    put(&mut output, &mut offset, &verified.capsule_hash())?;
    put(&mut output, &mut offset, &verified.state_root())?;
    put(
        &mut output,
        &mut offset,
        &(CAPSULE_ENCODED_LEN as u32).to_be_bytes(),
    )?;
    put(&mut output, &mut offset, &capsule_bytes)?;
    let mut hasher = Sha256::new();
    hasher.update(b"BOS/ROOT-RECORD/v3");
    hasher.update(&output[..offset]);
    let checksum: [u8; 32] = hasher.finalize().into();
    put(&mut output, &mut offset, &checksum)?;
    if offset != ROOT_RECORD_LEN {
        return Err(RecoveryError::RootStoreFailure);
    }
    Ok(output)
}

fn encode_selector_record(slot: RootSlot, verified: &VerifiedCapsule) -> [u8; SELECTOR_RECORD_LEN] {
    let mut output = [0u8; SELECTOR_RECORD_LEN];
    let mut offset = 0usize;
    // Fixed sizes make these writes infallible; retain explicit offsets so the
    // encoded format is independent of Rust struct layout.
    output[offset..offset + 8].copy_from_slice(&SELECTOR_MAGIC);
    offset += 8;
    output[offset] = slot as u8;
    offset += 8; // slot byte plus seven canonical zero bytes
    output[offset..offset + 8].copy_from_slice(&verified.sequence().to_be_bytes());
    offset += 8;
    output[offset..offset + 32].copy_from_slice(&verified.capsule_hash());
    offset += 32;
    output[offset..offset + 32].copy_from_slice(&verified.state_root());
    offset += 32;
    let mut hasher = Sha256::new();
    hasher.update(b"BOS/SELECTOR/v3");
    hasher.update(&output[..offset]);
    output[offset..offset + 32].copy_from_slice(&hasher.finalize());
    output
}

fn put(output: &mut [u8], offset: &mut usize, bytes: &[u8]) -> Result<(), RecoveryError> {
    let end = offset
        .checked_add(bytes.len())
        .ok_or(RecoveryError::ArithmeticOverflow)?;
    output
        .get_mut(*offset..end)
        .ok_or(RecoveryError::RootStoreFailure)?
        .copy_from_slice(bytes);
    *offset = end;
    Ok(())
}
