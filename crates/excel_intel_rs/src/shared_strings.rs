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
    pub generation: u32,
    pub payload: Box<str>,
    pub disk_offset: u64,
}

pub struct LruCache {
    slots: Vec<LruSlot>,
    free_head: Option<NonZeroU32>,
    map: hashbrown::HashMap<u32, (NonZeroU32, u32)>, // key -> (1-based slot index, generation)
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
        let &(nz_idx, gen) = self.map.get(&key)?;
        let idx = Self::slot_idx(nz_idx);
        if self.slots[idx].generation != gen || self.slots[idx].key != key {
            return None;
        }
        self.move_to_head(nz_idx);
        Some(&self.slots[idx].payload)
    }

    pub fn insert(&mut self, key: u32, offset: u64, s: String) {
        let payload_len = s.len();
        if payload_len > UNCACHEABLE_STRING_THRESHOLD {
            return;
        }

        // If key already exists, update payload and promote
        if let Some(&(nz_idx, gen)) = self.map.get(&key) {
            let idx = Self::slot_idx(nz_idx);
            if self.slots[idx].generation == gen && self.slots[idx].key == key {
                let old_len = self.slots[idx].payload.len();
                self.current_payload_bytes =
                    self.current_payload_bytes.saturating_sub(old_len) + payload_len;
                self.slots[idx].payload = s.into_boxed_str();
                self.slots[idx].disk_offset = offset;
                self.move_to_head(nz_idx);
                return;
            }
        }

        // Evict until within text bytes limit and entry count limit
        while (self.current_payload_bytes + payload_len > LRU_MAX_TEXT_BYTES
            || self.map.len() >= LRU_MAX_ENTRIES)
            && self.tail.is_some()
        {
            self.evict_tail();
        }

        let boxed_str = s.into_boxed_str();
        let (nz_idx, gen) = if let Some(free_nz) = self.free_head {
            let free_i = Self::slot_idx(free_nz);
            self.free_head = self.slots[free_i].next;
            let current_gen = self.slots[free_i].generation;
            self.slots[free_i] = LruSlot {
                key,
                prev: None,
                next: None,
                generation: current_gen,
                payload: boxed_str,
                disk_offset: offset,
            };
            (free_nz, current_gen)
        } else {
            let new_i = self.slots.len();
            let nz = Self::to_nonzero(new_i);
            self.slots.push(LruSlot {
                key,
                prev: None,
                next: None,
                generation: 1,
                payload: boxed_str,
                disk_offset: offset,
            });
            (nz, 1)
        };

        // Attach as head
        self.slots[Self::slot_idx(nz_idx)].next = self.head;
        if let Some(old_head) = self.head {
            self.slots[Self::slot_idx(old_head)].prev = Some(nz_idx);
        }
        self.head = Some(nz_idx);
        if self.tail.is_none() {
            self.tail = Some(nz_idx);
        }

        self.map.insert(key, (nz_idx, gen));
        self.current_payload_bytes += payload_len;
    }

    pub fn remove(&mut self, key: u32) -> Option<String> {
        let &(nz_idx, gen) = self.map.get(&key)?;
        let idx = Self::slot_idx(nz_idx);
        if self.slots[idx].generation != gen || self.slots[idx].key != key {
            return None;
        }

        self.map.remove(&key);
        let payload_len = self.slots[idx].payload.len();
        self.current_payload_bytes = self.current_payload_bytes.saturating_sub(payload_len);

        self.detach(nz_idx);

        let old_payload =
            std::mem::replace(&mut self.slots[idx].payload, String::new().into_boxed_str());

        // Harden generation counter: retire slot if generation overflows
        if let Some(next_gen) = self.slots[idx].generation.checked_add(1) {
            self.slots[idx].generation = next_gen;
            self.slots[idx].next = self.free_head;
            self.free_head = Some(nz_idx);
        } else {
            // Permanently retire slot: do not return to free_head, preventing wraparound/stale reuse
            self.slots[idx].generation = u32::MAX;
            self.slots[idx].next = None;
            self.slots[idx].prev = None;
        }

        Some(old_payload.into_string())
    }

    fn detach(&mut self, nz_idx: NonZeroU32) {
        let idx = Self::slot_idx(nz_idx);
        let prev_opt = self.slots[idx].prev;
        let next_opt = self.slots[idx].next;

        if let Some(prev) = prev_opt {
            self.slots[Self::slot_idx(prev)].next = next_opt;
        } else {
            self.head = next_opt;
        }

        if let Some(next) = next_opt {
            self.slots[Self::slot_idx(next)].prev = prev_opt;
        } else {
            self.tail = prev_opt;
        }

        self.slots[idx].prev = None;
        self.slots[idx].next = None;
    }

    fn move_to_head(&mut self, nz_idx: NonZeroU32) {
        if self.head == Some(nz_idx) {
            return;
        }

        self.detach(nz_idx);

        self.slots[Self::slot_idx(nz_idx)].next = self.head;
        self.slots[Self::slot_idx(nz_idx)].prev = None;

        if let Some(old_head) = self.head {
            self.slots[Self::slot_idx(old_head)].prev = Some(nz_idx);
        }
        self.head = Some(nz_idx);

        if self.tail.is_none() {
            self.tail = Some(nz_idx);
        }
    }

    fn evict_tail(&mut self) {
        if let Some(tail_nz) = self.tail {
            let tail_i = Self::slot_idx(tail_nz);
            let key = self.slots[tail_i].key;
            self.map.remove(&key);
            let payload_len = self.slots[tail_i].payload.len();
            self.current_payload_bytes = self.current_payload_bytes.saturating_sub(payload_len);

            self.detach(tail_nz);

            // Free payload memory and place slot onto free list if generation does not overflow
            self.slots[tail_i].payload = String::new().into_boxed_str();
            if let Some(next_gen) = self.slots[tail_i].generation.checked_add(1) {
                self.slots[tail_i].generation = next_gen;
                self.slots[tail_i].next = self.free_head;
                self.free_head = Some(tail_nz);
            } else {
                // Permanently retire slot: do not return to free_head, preventing wraparound/stale reuse
                self.slots[tail_i].generation = u32::MAX;
                self.slots[tail_i].next = None;
                self.slots[tail_i].prev = None;
            }
        }
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }

    pub fn current_payload_bytes(&self) -> usize {
        self.current_payload_bytes
    }

    pub fn clear(&mut self) {
        self.map.clear();
        self.slots.clear();
        self.head = None;
        self.tail = None;
        self.free_head = None;
        self.current_payload_bytes = 0;
    }

    #[cfg(test)]
    pub fn check_invariants(&self) {
        if self.map.is_empty() {
            assert!(self.head.is_none(), "Empty cache head must be None");
            assert!(self.tail.is_none(), "Empty cache tail must be None");
            assert_eq!(
                self.current_payload_bytes, 0,
                "Empty cache payload bytes must be 0"
            );
            return;
        }

        assert!(self.head.is_some(), "Non-empty cache head must be Some");
        assert!(self.tail.is_some(), "Non-empty cache tail must be Some");

        // Forward traverse head -> tail
        let mut forward_count = 0;
        let mut curr = self.head;
        let mut prev_seen = None;
        let mut sum_bytes = 0;

        while let Some(nz) = curr {
            forward_count += 1;
            let idx = Self::slot_idx(nz);
            assert_eq!(
                self.slots[idx].prev, prev_seen,
                "Slot prev pointer mismatch at index {}",
                idx
            );
            sum_bytes += self.slots[idx].payload.len();

            let &(map_nz, gen) = self
                .map
                .get(&self.slots[idx].key)
                .expect("Slot key must exist in lookup map");
            assert_eq!(map_nz, nz, "Map index mismatch for slot");
            assert_eq!(
                gen, self.slots[idx].generation,
                "Generation mismatch for slot"
            );

            prev_seen = Some(nz);
            curr = self.slots[idx].next;
        }

        assert_eq!(prev_seen, self.tail, "Forward traversal must end at tail");
        assert_eq!(
            forward_count,
            self.map.len(),
            "Forward traversal count must match map.len()"
        );
        assert_eq!(
            sum_bytes, self.current_payload_bytes,
            "Sum of payloads must match current_payload_bytes"
        );

        // Backward traverse tail -> head
        let mut backward_count = 0;
        let mut bcurr = self.tail;
        let mut next_seen = None;

        while let Some(nz) = bcurr {
            backward_count += 1;
            let idx = Self::slot_idx(nz);
            assert_eq!(
                self.slots[idx].next, next_seen,
                "Slot next pointer mismatch at index {}",
                idx
            );
            next_seen = Some(nz);
            bcurr = self.slots[idx].prev;
        }

        assert_eq!(next_seen, self.head, "Backward traversal must end at head");
        assert_eq!(
            backward_count, forward_count,
            "Backward traversal count must match forward count"
        );
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
                crate::memory_guard::check_memory_guard()?;
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
            crate::memory_guard::record_attributable_alloc(std::mem::size_of::<StringEntry>())?;
        } else {
            let offset = self.tier1_buf.len() as u64;
            self.tier1_buf.extend_from_slice(bytes);
            self.index_table.push(StringEntry {
                offset,
                len: str_len,
            });
            crate::memory_guard::record_attributable_alloc(
                bytes.len() + std::mem::size_of::<StringEntry>(),
            )?;
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
        assert_eq!(std::mem::size_of::<Box<str>>(), 16);
        assert_eq!(std::mem::size_of::<u64>(), 8);
    }

    #[test]
    fn test_empty_cache_behavior() {
        let mut lru = LruCache::new();
        assert!(lru.is_empty());
        assert_eq!(lru.len(), 0);
        assert_eq!(lru.current_payload_bytes(), 0);
        assert_eq!(lru.get(42), None);
        assert_eq!(lru.remove(42), None);
        lru.check_invariants();
    }

    #[test]
    fn test_single_entry_insertion_and_retrieval() {
        let mut lru = LruCache::new();
        lru.insert(1, 100, "hello".to_string());
        assert!(!lru.is_empty());
        assert_eq!(lru.len(), 1);
        assert_eq!(lru.current_payload_bytes(), 5);
        assert_eq!(lru.get(1), Some("hello"));
        lru.check_invariants();

        assert_eq!(lru.remove(1), Some("hello".to_string()));
        assert!(lru.is_empty());
        assert_eq!(lru.len(), 0);
        assert_eq!(lru.current_payload_bytes(), 0);
        lru.check_invariants();
    }

    #[test]
    fn test_head_tail_middle_node_promotion() {
        let mut lru = LruCache::new();
        lru.insert(1, 10, "first".to_string());
        lru.insert(2, 20, "second".to_string());
        lru.insert(3, 30, "third".to_string());
        lru.check_invariants();
        // Head is 3, tail is 1. Order: 3 -> 2 -> 1

        // 1. Promote head (key 3)
        assert_eq!(lru.get(3), Some("third"));
        lru.check_invariants();
        assert_eq!(
            lru.head.map(LruCache::slot_idx),
            lru.map.get(&3).map(|&(nz, _)| LruCache::slot_idx(nz))
        );

        // 2. Promote tail (key 1)
        assert_eq!(lru.get(1), Some("first"));
        lru.check_invariants();
        // Now head is 1, order: 1 -> 3 -> 2, tail is 2
        assert_eq!(
            lru.head.map(LruCache::slot_idx),
            lru.map.get(&1).map(|&(nz, _)| LruCache::slot_idx(nz))
        );
        assert_eq!(
            lru.tail.map(LruCache::slot_idx),
            lru.map.get(&2).map(|&(nz, _)| LruCache::slot_idx(nz))
        );

        // 3. Promote middle (key 3)
        assert_eq!(lru.get(3), Some("third"));
        lru.check_invariants();
        // Now head is 3, order: 3 -> 1 -> 2
        assert_eq!(
            lru.head.map(LruCache::slot_idx),
            lru.map.get(&3).map(|&(nz, _)| LruCache::slot_idx(nz))
        );
    }

    #[test]
    fn test_rapid_eviction_with_100k_insertions() {
        let mut lru = LruCache::new();
        // Rapidly insert 100,000 distinct items
        for i in 0..100_000 {
            lru.insert(i, (i * 10) as u64, format!("str_{}", i));
            if i % 10_000 == 0 {
                lru.check_invariants();
            }
        }
        lru.check_invariants();

        // Must never exceed LRU_MAX_ENTRIES (50,000)
        assert_eq!(lru.len(), LRU_MAX_ENTRIES);
        assert!(lru.current_payload_bytes() <= LRU_MAX_TEXT_BYTES);

        // Earliest keys (0..50,000) should have been evicted
        assert!(lru.get(0).is_none());
        assert!(lru.get(49_999).is_none());
        // Latest keys (50,000..100,000) must be present
        assert_eq!(lru.get(99_999), Some("str_99999"));
        assert_eq!(lru.get(50_000), Some("str_50000"));
        lru.check_invariants();
    }

    #[test]
    fn test_repeated_insertion_and_removal() {
        let mut lru = LruCache::new();
        for round in 0usize..5 {
            for i in 0..100 {
                let key = (round * 100 + i) as u32;
                lru.insert(key, key as u64, format!("val_{}", key));
            }
            lru.check_invariants();

            for i in 0..50 {
                let key = (round * 100 + i) as u32;
                let removed = lru.remove(key);
                assert_eq!(removed, Some(format!("val_{}", key)));
            }
            lru.check_invariants();
            assert_eq!(lru.len(), (round + 1) * 50);
        }
        lru.check_invariants();
        assert_eq!(lru.len(), 250);
    }

    #[test]
    fn test_freelist_slot_reuse() {
        let mut lru = LruCache::new();
        // Insert 10 items
        for i in 0..10 {
            lru.insert(i, i as u64, format!("item_{}", i));
        }
        assert_eq!(lru.slots.len(), 10);
        lru.check_invariants();

        // Remove 5 items
        for i in 0..5 {
            assert!(lru.remove(i).is_some());
        }
        assert_eq!(lru.len(), 5);
        lru.check_invariants();

        // Insert 5 new items — must reuse slots from free list without growing arena
        for i in 10..15 {
            lru.insert(i, i as u64, format!("item_{}", i));
        }
        assert_eq!(lru.slots.len(), 10); // Arena capacity/len did NOT grow!
        assert_eq!(lru.len(), 10);
        lru.check_invariants();

        // Verify all 10 items are accessible
        for i in 5..15 {
            assert_eq!(lru.get(i), Some(format!("item_{}", i)).as_deref());
        }
    }

    #[test]
    fn test_payload_byte_accounting() {
        let mut lru = LruCache::new();
        lru.insert(1, 0, "a".repeat(100));
        assert_eq!(lru.current_payload_bytes(), 100);

        lru.insert(2, 0, "b".repeat(250));
        assert_eq!(lru.current_payload_bytes(), 350);

        // Update key 1 with larger payload
        lru.insert(1, 0, "a".repeat(150));
        assert_eq!(lru.current_payload_bytes(), 400);

        // Remove key 2
        lru.remove(2);
        assert_eq!(lru.current_payload_bytes(), 150);

        lru.remove(1);
        assert_eq!(lru.current_payload_bytes(), 0);
        lru.check_invariants();
    }

    #[test]
    fn test_16mib_payload_limit() {
        let mut lru = LruCache::new();
        let payload_size = 30 * 1024; // 30 KB strings (<= 32 KB threshold)
        let sample = "x".repeat(payload_size);

        // Insert until exceeding 16 MiB
        let total_needed = (17 * 1024 * 1024) / payload_size;
        for i in 0..total_needed {
            lru.insert(i as u32, 0, sample.clone());
        }

        // Must strictly preserve LRU_MAX_TEXT_BYTES limit
        assert!(lru.current_payload_bytes() <= LRU_MAX_TEXT_BYTES);
        lru.check_invariants();
    }

    #[test]
    fn test_50000_entry_limit() {
        let mut lru = LruCache::new();
        // Insert 60,000 tiny strings (total bytes << 16 MiB)
        for i in 0..60_000 {
            lru.insert(i, 0, "a".to_string());
        }

        assert_eq!(lru.len(), LRU_MAX_ENTRIES);
        assert_eq!(lru.current_payload_bytes(), LRU_MAX_ENTRIES);
        lru.check_invariants();

        // First 10,000 items (0..10,000) must be evicted
        for i in 0..10_000 {
            assert!(lru.get(i).is_none());
        }
        // Last 50,000 items (10,000..60,000) must remain
        for i in 10_000..60_000 {
            assert_eq!(lru.get(i), Some("a"));
        }
    }

    #[test]
    fn test_cache_destruction_and_memory_cleanup() {
        let mut lru = LruCache::new();
        for i in 0..1000 {
            lru.insert(i, 0, format!("text_{}", i));
        }
        assert_eq!(lru.len(), 1000);
        assert!(lru.current_payload_bytes() > 0);

        lru.clear();
        assert_eq!(lru.len(), 0);
        assert!(lru.is_empty());
        assert_eq!(lru.current_payload_bytes(), 0);
        lru.check_invariants();
    }

    #[test]
    fn test_lru_arena_rapid_eviction_and_reuse() {
        let mut lru = LruCache::new();
        for i in 0..100 {
            lru.insert(i, (i * 100) as u64, format!("value_{:090}", i));
        }
        assert_eq!(lru.len(), 100);

        // Access middle item and verify promotion
        assert!(lru.get(50).is_some());
        assert_eq!(
            lru.head.map(LruCache::slot_idx),
            lru.map
                .get(&50)
                .copied()
                .map(|(nz, _)| LruCache::slot_idx(nz))
        );
    }

    #[test]
    fn test_shared_strings_tier1_to_tier2_spill_transition() {
        let mut table = SharedStringsTable::new();
        for i in 0..105_000 {
            let idx = table.push_string(&format!("str_{}", i)).unwrap();
            assert_eq!(idx, i as u32);
        }

        assert_eq!(table.len(), 105_000);
        assert_eq!(table.get_string(10).unwrap(), "str_10");
        assert_eq!(table.get_string(102_000).unwrap(), "str_102000");
    }

    #[test]
    fn test_shared_strings_ceiling_2m_rejection() {
        let mut table = SharedStringsTable::new();
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
        for i in 0..100_005 {
            table.push_string(&format!("item_{:05}", i)).unwrap();
        }

        let table_arc = Arc::new(table);
        let target_idx = 100_002;

        let initial_disk_reads = table_arc.disk_read_count();
        let mut handles = Vec::new();

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
        assert_eq!(final_disk_reads - initial_disk_reads, 1);
    }

    #[test]
    fn test_generation_counter_overflow_permanently_retires_slot() {
        let mut lru = LruCache::new();
        lru.insert(1, 0, "first".to_string());
        assert_eq!(lru.len(), 1);
        assert_eq!(lru.slots.len(), 1);

        // Manually simulate generation counter at u32::MAX
        lru.slots[0].generation = u32::MAX;
        // Update map entry to reflect this generation for valid lookup
        if let Some(entry) = lru.map.get_mut(&1) {
            entry.1 = u32::MAX;
        }

        // Remove item 1 — next_gen overflows, slot 0 must be retired permanently
        let removed = lru.remove(1);
        assert_eq!(removed, Some("first".to_string()));
        assert_eq!(lru.len(), 0);
        // Crucial invariant: free_head must NOT contain the overflowed slot
        assert_eq!(lru.free_head, None);
        assert_eq!(lru.slots[0].generation, u32::MAX);

        // Inserting a new item must allocate a NEW slot in the arena, NOT reuse slot 0
        lru.insert(2, 0, "second".to_string());
        assert_eq!(lru.len(), 1);
        assert_eq!(lru.slots.len(), 2); // Arena grew from 1 to 2 because slot 0 was retired!
        assert_eq!(lru.slots[1].key, 2);
        assert_eq!(lru.get(2), Some("second"));

        // Stale handle with slot 0 cannot retrieve data
        assert_eq!(lru.get(1), None);
        lru.check_invariants();
    }
}
