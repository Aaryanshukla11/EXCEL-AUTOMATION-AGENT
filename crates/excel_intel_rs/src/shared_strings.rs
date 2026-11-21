use crate::cell_validator::validate_cell_string;
use crate::error::RustParserError;
use crate::scratch::ScratchSpillFile;
use std::io::{Read, Seek, SeekFrom, Write};
use std::num::NonZeroU32;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

pub const MAX_SHARED_STRINGS_COUNT: usize = 2_000_000;
pub const TIER1_MAX_BYTES: usize = 32 * 1024 * 1024; // 32.0 MiB
pub const TIER1_SPILL_ENTRY_THRESHOLD: usize = 100_000;
pub const TIER2_MAX_DISK_BYTES: u64 = 512 * 1024 * 1024; // 512.0 MiB disk capacity limit
pub const LRU_MAX_TEXT_BYTES: usize = 16 * 1024 * 1024; // 16.0 MiB
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
pub struct LruSlot {
    pub key: u32,
    pub prev: Option<NonZeroU32>, // 1-based index (0x0 niche optimized)
    pub next: Option<NonZeroU32>, // 1-based index (0x0 niche optimized)
    pub _padding: u32,
    pub payload: Box<str>,
    pub disk_offset: u64,
}

pub struct LruCache {
    slots: Vec<LruSlot>,
    free_head: Option<NonZeroU32>,
    map: hashbrown::HashMap<u32, NonZeroU32>, // key -> 1-based slot index
    head: Option<NonZeroU32>,
    tail: Option<NonZeroU32>,
    current_payload_bytes: usize,
}

impl LruCache {
    pub fn new() -> Self {
        Self {
            slots: Vec::with_capacity(1024),
            free_head: None,
            map: hashbrown::HashMap::with_capacity(1024),
            head: None,
            tail: None,
            current_payload_bytes: 0,
        }
    }

    #[inline]
    fn slot_idx(nz: NonZeroU32) -> usize {
        (nz.get() - 1) as usize
    }

    #[inline]
    fn to_nonzero(idx: usize) -> NonZeroU32 {
        NonZeroU32::new((idx + 1) as u32).expect("Slot index overflow")
    }

    pub fn get(&mut self, key: u32) -> Option<&str> {
        let &nz_idx = self.map.get(&key)?;
        self.move_to_head(nz_idx);
        let idx = Self::slot_idx(nz_idx);
        Some(&self.slots[idx].payload)
    }

    pub fn insert(&mut self, key: u32, offset: u64, s: String) {
        let payload_len = s.len();
        if payload_len > UNCACHEABLE_STRING_THRESHOLD {
            return;
        }

        // If key already exists, update payload and promote
        if let Some(&nz_idx) = self.map.get(&key) {
            let idx = Self::slot_idx(nz_idx);
            let old_len = self.slots[idx].payload.len();
            self.current_payload_bytes =
                self.current_payload_bytes.saturating_sub(old_len) + payload_len;
            self.slots[idx].payload = s.into_boxed_str();
            self.slots[idx].disk_offset = offset;
            self.move_to_head(nz_idx);
            return;
        }

        // Evict until within text bytes limit and entry count limit
        while (self.current_payload_bytes + payload_len > LRU_MAX_TEXT_BYTES
            || self.map.len() >= LRU_MAX_ENTRIES)
            && self.tail.is_some()
        {
            self.evict_tail();
        }

        let boxed_str = s.into_boxed_str();
        let nz_idx = if let Some(free_nz) = self.free_head {
            let free_i = Self::slot_idx(free_nz);
            self.free_head = self.slots[free_i].next;
            self.slots[free_i] = LruSlot {
                key,
                prev: None,
                next: self.head,
                _padding: 0,
                payload: boxed_str,
                disk_offset: offset,
            };
            free_nz
        } else {
            let new_i = self.slots.len();
            let nz = Self::to_nonzero(new_i);
            self.slots.push(LruSlot {
                key,
                prev: None,
                next: self.head,
                _padding: 0,
                payload: boxed_str,
                disk_offset: offset,
            });
            nz
        };

        if let Some(old_head) = self.head {
            self.slots[Self::slot_idx(old_head)].prev = Some(nz_idx);
        }
        self.head = Some(nz_idx);
        if self.tail.is_none() {
            self.tail = Some(nz_idx);
        }

        self.map.insert(key, nz_idx);
        self.current_payload_bytes += payload_len;
    }

    fn move_to_head(&mut self, nz_idx: NonZeroU32) {
        if self.head == Some(nz_idx) {
            return;
        }

        let idx = Self::slot_idx(nz_idx);
        let prev_opt = self.slots[idx].prev;
        let next_opt = self.slots[idx].next;

        if let Some(prev) = prev_opt {
            self.slots[Self::slot_idx(prev)].next = next_opt;
        }
        if let Some(next) = next_opt {
            self.slots[Self::slot_idx(next)].prev = prev_opt;
        } else {
            self.tail = prev_opt;
        }

        self.slots[idx].prev = None;
        self.slots[idx].next = self.head;

        if let Some(old_head) = self.head {
            self.slots[Self::slot_idx(old_head)].prev = Some(nz_idx);
        }
        self.head = Some(nz_idx);
    }

    fn evict_tail(&mut self) {
        if let Some(tail_nz) = self.tail {
            let tail_i = Self::slot_idx(tail_nz);
            self.map.remove(&self.slots[tail_i].key);
            self.current_payload_bytes = self
                .current_payload_bytes
                .saturating_sub(self.slots[tail_i].payload.len());

            self.tail = self.slots[tail_i].prev;
            if let Some(new_tail) = self.tail {
                self.slots[Self::slot_idx(new_tail)].next = None;
            } else {
                self.head = None;
            }

            // Free payload memory and place slot onto free list
            self.slots[tail_i].payload = String::new().into_boxed_str();
            self.slots[tail_i].next = self.free_head;
            self.free_head = Some(tail_nz);
        }
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }
}

impl Default for LruCache {
    fn default() -> Self {
        Self::new()
    }
}

pub struct SharedStringsTable {
    index_table: Vec<StringEntry>,
    tier1_buf: Vec<u8>,
    spill_file: Option<Mutex<ScratchSpillFile>>,
    spill_offset: u64,
    lru: Mutex<LruCache>,
    disk_read_count: AtomicUsize,
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
            disk_read_count: AtomicUsize::new(0),
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

            let new_spill_offset = self.spill_offset + (bytes.len() as u64);
            if new_spill_offset > TIER2_MAX_DISK_BYTES {
                return Err(RustParserError::ResourceLimit {
                    code: "ERR_DISK_SPILL_QUOTA_EXCEEDED",
                    message: format!(
                        "Tier 2 disk spill limit ({} MiB) exceeded",
                        TIER2_MAX_DISK_BYTES / (1024 * 1024)
                    ),
                });
            }

            let disk_offset = self.spill_offset;
            let mut file_guard = self.spill_file.as_ref().unwrap().lock().unwrap();
            file_guard.file.write_all(bytes).map_err(|e| {
                RustParserError::CorruptWorkbook(format!(
                    "Failed to spill shared string to disk: {}",
                    e
                ))
            })?;
            self.spill_offset = new_spill_offset;

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
            // Tier 1 direct RAM lookup (lock-free)
            let start = entry.offset as usize;
            let end = start + (entry.len as usize);
            let slice = std::str::from_utf8(&self.tier1_buf[start..end]).map_err(|_| {
                RustParserError::CorruptWorkbook(format!("Corrupt UTF-8 at index {}", index))
            })?;
            Ok(slice.to_string())
        } else {
            // Tier 2 Disk/LRU lookup with Double-Checked Locking
            // 1. First check in LRU under L2 lock
            {
                let mut lru = self.lru.lock().unwrap();
                if let Some(cached) = lru.get(index) {
                    return Ok(cached.to_string());
                }
            }

            // 2. Acquire L1 (ScratchSpillFile lock) for disk access
            let disk_offset = entry.offset & !IS_TIER2_DISK_FLAG;
            let spill_file_mutex = self.spill_file.as_ref().ok_or_else(|| {
                RustParserError::CorruptWorkbook(
                    "Spill file not initialized for Tier 2 lookup".to_string(),
                )
            })?;
            let mut file_guard = spill_file_mutex.lock().unwrap();

            // 3. Double-check LRU under L2 lock: another thread may have read this index while we waited for L1
            {
                let mut lru = self.lru.lock().unwrap();
                if let Some(cached) = lru.get(index) {
                    return Ok(cached.to_string());
                }
            }

            // 4. Seek and read exactly once from disk
            file_guard
                .file
                .seek(SeekFrom::Start(disk_offset))
                .map_err(|e| RustParserError::CorruptWorkbook(format!("Disk seek error: {}", e)))?;

            let mut buf = vec![0u8; entry.len as usize];
            file_guard
                .file
                .read_exact(&mut buf)
                .map_err(|e| RustParserError::CorruptWorkbook(format!("Disk read error: {}", e)))?;

            self.disk_read_count.fetch_add(1, Ordering::SeqCst);

            let s = String::from_utf8(buf).map_err(|_| {
                RustParserError::CorruptWorkbook(format!(
                    "Corrupt spilled UTF-8 at index {}",
                    index
                ))
            })?;

            // 5. Insert into LRU under L2 lock
            {
                let mut lru = self.lru.lock().unwrap();
                lru.insert(index, disk_offset, s.clone());
            }

            Ok(s)
        }
    }

    pub fn disk_read_count(&self) -> usize {
        self.disk_read_count.load(Ordering::SeqCst)
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_lru_slot_layout_size_is_40_bytes() {
        assert_eq!(std::mem::size_of::<LruSlot>(), 40);
        assert_eq!(std::mem::size_of::<Option<NonZeroU32>>(), 4);
    }

    #[test]
    fn test_lru_arena_rapid_eviction_and_reuse() {
        let mut lru = LruCache::new();
        // Insert 100 strings of 100 bytes each
        for i in 0..100 {
            lru.insert(i, (i * 100) as u64, format!("value_{:090}", i));
        }
        assert_eq!(lru.len(), 100);

        // Access middle item and verify promotion
        assert!(lru.get(50).is_some());
        assert_eq!(
            lru.head.map(LruCache::slot_idx),
            lru.map.get(&50).copied().map(LruCache::slot_idx)
        );
    }

    #[test]
    fn test_shared_strings_tier1_to_tier2_spill_transition() {
        let mut table = SharedStringsTable::new();
        // Populate up to spill threshold
        for i in 0..105_000 {
            let idx = table.push_string(&format!("str_{}", i)).unwrap();
            assert_eq!(idx, i as u32);
        }

        assert_eq!(table.len(), 105_000);
        // Verify Tier 1 lookup (RAM)
        assert_eq!(table.get_string(10).unwrap(), "str_10");
        // Verify Tier 2 lookup (Disk / LRU)
        assert_eq!(table.get_string(102_000).unwrap(), "str_102000");
    }

    #[test]
    fn test_shared_strings_ceiling_2m_rejection() {
        let mut table = SharedStringsTable::new();
        // Manually simulate reaching 2,000,000 entries
        table
            .index_table
            .resize(MAX_SHARED_STRINGS_COUNT, StringEntry { offset: 0, len: 5 });

        let res = table.push_string("overflow");
        assert!(res.is_err());
        match res.unwrap_err() {
            RustParserError::ResourceLimit { code, .. } => {
                assert_eq!(code, "ERR_SHARED_STRINGS_OVERFLOW");
            }
            _ => panic!("Expected ResourceLimit ERR_SHARED_STRINGS_OVERFLOW"),
        }
    }

    #[test]
    fn test_concurrent_same_index_single_disk_read() {
        let mut table = SharedStringsTable::new();
        // Force Tier 2 entry
        for i in 0..100_005 {
            table.push_string(&format!("item_{:05}", i)).unwrap();
        }

        let table_arc = Arc::new(table);
        let target_idx = 100_002;

        let initial_disk_reads = table_arc.disk_read_count();
        let mut handles = Vec::new();

        // Spawn 8 concurrent threads querying the exact same cold index
        for _ in 0..8 {
            let t = Arc::clone(&table_arc);
            handles.push(thread::spawn(move || {
                let s = t.get_string(target_idx).unwrap();
                assert_eq!(s, "item_100002");
            }));
        }

        for h in handles {
            h.join().unwrap();
        }

        let final_disk_reads = table_arc.disk_read_count();
        // Crucial Double-Checked Locking Assertion: exactly 1 physical disk read executed across all 8 threads!
        assert_eq!(final_disk_reads - initial_disk_reads, 1);
    }
}
