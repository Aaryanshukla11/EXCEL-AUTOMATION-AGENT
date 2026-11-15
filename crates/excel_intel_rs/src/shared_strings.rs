use crate::cell_validator::validate_cell_string;
use crate::error::RustParserError;
use crate::scratch::ScratchSpillFile;
use std::io::{Read, Seek, SeekFrom, Write};
use std::ptr::NonNull;
use std::sync::Mutex;

pub const MAX_SHARED_STRINGS_COUNT: usize = 2_000_000;
pub const TIER1_MAX_BYTES: usize = 32 * 1024 * 1024; // 32.0 MB
pub const TIER1_SPILL_ENTRY_THRESHOLD: usize = 100_000;
pub const LRU_MAX_TEXT_BYTES: usize = 16 * 1024 * 1024; // 16.0 MB
pub const LRU_MAX_ENTRIES: usize = 50_000;
pub const UNCACHEABLE_STRING_THRESHOLD: usize = 32 * 1024; // 32 KB

const IS_TIER2_DISK_FLAG: u64 = 1 << 63;

#[derive(Clone, Copy, Debug)]
#[repr(C)]
pub struct StringEntry {
    pub offset: u64,
    pub len: u32,
}

#[repr(C)]
struct LruNode {
    offset: u64,
    prev: Option<NonNull<LruNode>>,
    next: Option<NonNull<LruNode>>,
    payload: Box<str>,
    key: u32,
    len: u32,
}

struct LruCache {
    nodes: hashbrown::HashMap<u32, NonNull<LruNode>>,
    head: Option<NonNull<LruNode>>,
    tail: Option<NonNull<LruNode>>,
    current_payload_bytes: usize,
}

unsafe impl Send for LruCache {}

impl LruCache {
    fn new() -> Self {
        Self {
            nodes: hashbrown::HashMap::with_capacity(1024),
            head: None,
            tail: None,
            current_payload_bytes: 0,
        }
    }

    fn get(&mut self, key: u32) -> Option<&str> {
        let node_ptr = *self.nodes.get(&key)?;
        self.move_to_head(node_ptr);
        unsafe { Some(&(*node_ptr.as_ptr()).payload) }
    }

    fn insert(&mut self, key: u32, offset: u64, len: u32, s: String) {
        let payload_len = s.len();
        if payload_len > UNCACHEABLE_STRING_THRESHOLD {
            return;
        }

        // Evict until within limits
        while (self.current_payload_bytes + payload_len > LRU_MAX_TEXT_BYTES
            || self.nodes.len() >= LRU_MAX_ENTRIES)
            && self.tail.is_some()
        {
            self.evict_tail();
        }

        let boxed_str = s.into_boxed_str();
        let node = Box::new(LruNode {
            key,
            offset,
            len,
            prev: None,
            next: self.head,
            payload: boxed_str,
        });

        let node_ptr = NonNull::new(Box::into_raw(node)).unwrap();
        if let Some(mut old_head) = self.head {
            unsafe { old_head.as_mut().prev = Some(node_ptr) };
        }
        self.head = Some(node_ptr);
        if self.tail.is_none() {
            self.tail = Some(node_ptr);
        }

        self.nodes.insert(key, node_ptr);
        self.current_payload_bytes += payload_len;
    }

    fn move_to_head(&mut self, mut node_ptr: NonNull<LruNode>) {
        if self.head == Some(node_ptr) {
            return;
        }

        unsafe {
            let node = node_ptr.as_mut();
            if let Some(mut prev) = node.prev {
                prev.as_mut().next = node.next;
            }
            if let Some(mut next) = node.next {
                next.as_mut().prev = node.prev;
            } else {
                self.tail = node.prev;
            }

            node.prev = None;
            node.next = self.head;
            if let Some(mut old_head) = self.head {
                old_head.as_mut().prev = Some(node_ptr);
            }
            self.head = Some(node_ptr);
        }
    }

    fn evict_tail(&mut self) {
        if let Some(tail_ptr) = self.tail {
            unsafe {
                let tail = Box::from_raw(tail_ptr.as_ptr());
                self.nodes.remove(&tail.key);
                self.current_payload_bytes = self
                    .current_payload_bytes
                    .saturating_sub(tail.payload.len());

                self.tail = tail.prev;
                if let Some(mut new_tail) = self.tail {
                    new_tail.as_mut().next = None;
                } else {
                    self.head = None;
                }
            }
        }
    }
}

impl Drop for LruCache {
    fn drop(&mut self) {
        let mut curr = self.head;
        while let Some(ptr) = curr {
            unsafe {
                let node = Box::from_raw(ptr.as_ptr());
                curr = node.next;
            }
        }
    }
}

pub struct SharedStringsTable {
    index_table: Vec<StringEntry>,
    tier1_buf: Vec<u8>,
    spill_file: Option<Mutex<ScratchSpillFile>>,
    spill_offset: u64,
    lru: Mutex<LruCache>,
}

unsafe impl Send for SharedStringsTable {}
unsafe impl Sync for SharedStringsTable {}

impl SharedStringsTable {
    pub fn new() -> Self {
        Self {
            index_table: Vec::with_capacity(1024),
            tier1_buf: Vec::with_capacity(1024),
            spill_file: None,
            spill_offset: 0,
            lru: Mutex::new(LruCache::new()),
        }
    }

    pub fn push_string(&mut self, s: &str) -> Result<u32, RustParserError> {
        validate_cell_string(s)?;

        let current_count = self.index_table.len();
        if current_count >= MAX_SHARED_STRINGS_COUNT {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_SHARED_STRINGS_OVERFLOW",
                message: format!(
                    "Shared strings count exceeds maximum limit of {}",
                    MAX_SHARED_STRINGS_COUNT
                ),
            });
        }

        let bytes = s.as_bytes();
        let str_len = bytes.len() as u32;

        let is_tier2 = self.spill_file.is_some()
            || (self.tier1_buf.len() + bytes.len() > TIER1_MAX_BYTES)
            || (current_count >= TIER1_SPILL_ENTRY_THRESHOLD);

        if is_tier2 {
            if self.spill_file.is_none() {
                self.spill_file = Some(Mutex::new(ScratchSpillFile::new()?));
            }

            let disk_offset = self.spill_offset;
            let mut file_guard = self.spill_file.as_ref().unwrap().lock().unwrap();
            file_guard.file.write_all(bytes).map_err(|e| {
                RustParserError::CorruptWorkbook(format!(
                    "Failed to spill shared string to disk: {}",
                    e
                ))
            })?;
            self.spill_offset += bytes.len() as u64;

            self.index_table.push(StringEntry {
                offset: disk_offset | IS_TIER2_DISK_FLAG,
                len: str_len,
            });
        } else {
            let offset = self.tier1_buf.len() as u64;
            self.tier1_buf.extend_from_slice(bytes);
            self.index_table.push(StringEntry {
                offset,
                len: str_len,
            });
        }

        Ok(current_count as u32)
    }

    pub fn get_string(&self, index: u32) -> Result<String, RustParserError> {
        let entry = self.index_table.get(index as usize).ok_or_else(|| {
            RustParserError::CorruptWorkbook(format!("Invalid shared string index: {}", index))
        })?;

        if (entry.offset & IS_TIER2_DISK_FLAG) == 0 {
            // Tier 1 direct RAM lookup
            let start = entry.offset as usize;
            let end = start + (entry.len as usize);
            let slice = std::str::from_utf8(&self.tier1_buf[start..end]).map_err(|_| {
                RustParserError::CorruptWorkbook(format!("Corrupt UTF-8 at index {}", index))
            })?;
            Ok(slice.to_string())
        } else {
            // Tier 2 Disk/LRU lookup
            let mut lru = self.lru.lock().unwrap();
            if let Some(cached) = lru.get(index) {
                return Ok(cached.to_string());
            }

            let disk_offset = entry.offset & !IS_TIER2_DISK_FLAG;
            let mut file_guard = self.spill_file.as_ref().unwrap().lock().unwrap();
            file_guard
                .file
                .seek(SeekFrom::Start(disk_offset))
                .map_err(|e| RustParserError::CorruptWorkbook(format!("Disk seek error: {}", e)))?;

            let mut buf = vec![0u8; entry.len as usize];
            file_guard
                .file
                .read_exact(&mut buf)
                .map_err(|e| RustParserError::CorruptWorkbook(format!("Disk read error: {}", e)))?;

            let s = String::from_utf8(buf).map_err(|_| {
                RustParserError::CorruptWorkbook(format!(
                    "Corrupt spilled UTF-8 at index {}",
                    index
                ))
            })?;

            lru.insert(index, disk_offset, entry.len, s.clone());
            Ok(s)
        }
    }

    pub fn len(&self) -> usize {
        self.index_table.len()
    }

    pub fn is_empty(&self) -> bool {
        self.index_table.is_empty()
    }
}

impl Default for SharedStringsTable {
    fn default() -> Self {
        Self::new()
    }
}
