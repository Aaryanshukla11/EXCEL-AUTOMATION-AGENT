# M02 — SPRINT 2 PLAN v2.2 TECHNICAL CORRECTION ADDENDUM

**Milestone:** M02 — Rust Streaming Parser  
**Document:** Sprint 2 Technical Correction Addendum (v2.2)  
**Governance State:** Sprint 1 Accepted and Frozen. **Zero production code modified.**

---

## 1. Technical Corrections

### 1.1 Correction 1: `LruSlot` Layout, `Option<NonZeroU32>` & Unit Standardization

#### Empirical Layout Verification via Rust Compiler
The exact memory layout was verified against `rustc`:
```rust
use std::num::NonZeroU32;

// Standard Option<u32>: 4-byte payload + 4-byte discriminant/padding = 8 bytes
// Option<NonZeroU32>: 4-byte payload utilizing 0x0 as the niche = 4 bytes (0% overhead)
#[repr(C)]
pub struct LruSlot {
    pub key: u32,                         // 4 bytes (shared string index)
    pub prev: Option<NonZeroU32>,          // 4 bytes (1-based arena index; niche-optimized)
    pub next: Option<NonZeroU32>,          // 4 bytes (1-based arena index; niche-optimized)
    pub _padding: u32,                    // 4 bytes (explicit alignment to 8 bytes)
    pub payload: Box<str>,                // 16 bytes (ptr: 8 bytes, len: 8 bytes)
    pub disk_offset: u64,                 // 8 bytes (offset in spill file)
}                                         // Total = 40 bytes (verified: size_of::<LruSlot>() == 40)
```
- By using 1-based indexing for arena slots ($1 \le \text{slot} \le 50{,}000$, where `None` is represented by `0x00000000`), `std::mem::size_of::<LruSlot>()` is strictly **40 bytes** (down from 48 bytes if unoptimized `Option<u32>` were used).
- For 50,000 entries: $50{,}000 \times 40\text{ bytes} = 2{,}000{,}000\text{ bytes} \approx \mathbf{1.907\text{ MiB}}$ ($2.000\text{ MB}$).

#### Corrected Memory Budget in Consistent MiB and Bytes

| Component | Specification / Limits | Size in MiB | Size in Bytes | Status |
|---|---|---|---|---|
| **Tier 1 RAM Text Buffer** | `TIER1_MAX_BYTES` (32.0 MiB) | $32.00\text{ MiB}$ | $33{,}554{,}432\text{ B}$ | **Enforced Limit** |
| **Tier 2 LRU Text Payload** | `LRU_MAX_TEXT_BYTES` (16.0 MiB) | $16.00\text{ MiB}$ | $16{,}777{,}216\text{ B}$ | **Enforced Limit** |
| **Shared-Strings Index Table** | $2\text{M} \times 16\text{ bytes}$ (`StringEntry`) | $30.52\text{ MiB}$ | $32{,}000{,}000\text{ B}$ | **Layout-Enforced Limit** |
| **LRU Safe Arena (`LruSlot`)** | $50\text{K} \times 40\text{ bytes}$ | $1.91\text{ MiB}$ | $2{,}000{,}000\text{ B}$ | *Calculated Layout* |
| **LRU SwissTable (`HashMap`)** | $65{,}536\text{ buckets} \times 9\text{ bytes}$ | $0.56\text{ MiB}$ | $589{,}824\text{ B}$ | *Calculated Layout* |
| **ZIP & Decompress Buffers** | `BufReader` (64 KB) + XML + inflate | $0.24\text{ MiB}$ | $256{,}000\text{ B}$ | *Configured Estimate* |
| **Row Chunk & PyObjects** | 1,000 rows $\times \approx 20\text{ cells}$ | $3.81\text{ MiB}$ | $4{,}000{,}000\text{ B}$ | *Transient Estimate* |
| **Allocator Overhead & Padding** | Heap fragmentation & metadata ($\approx 12\%$) | $10.15\text{ MiB}$ | $10{,}645{,}000\text{ B}$ | *Empirical Estimate* |
| **Total Estimated Peak Footprint** | Upper bound at 2,000,000 string capacity | **$\mathbf{95.19\text{ MiB}}$** | $\mathbf{99{,}822{,}472\text{ B}}$ | *Estimated Upper Bound* |

*Note: All estimates are subject to physical empirical verification against `BENCH-SCALE-100K.xlsx` during Sprint 2 acceptance testing.*

---

### 1.2 Correction 2: OS-Native Process Identity Validation & Safe Scavenging

#### Native Start-Time Protocol (No Heterogeneous Clock Conversion)
To eliminate invalid comparisons between incompatible clock domains:
- **Windows Protocol:**
  - When creating a scratch file, the process queries its own creation time via Win32 `GetProcessTimes(GetCurrentProcess(), &creation_ft, ...)` and encodes `creation_ft.dwLowDateTime` / `dwHighDateTime` directly as a 64-bit unsigned integer in the filename:
    $$\texttt{m02\_spill\_<pid>\_<win\_filetime\_u64>\_<uuid>.lock}$$
  - The scavenger queries the candidate PID's creation time via `GetProcessTimes(hProcess, &target_ft, ...)` and compares:
    $$\text{target\_ft as u64} == \text{filename\_filetime\_u64}$$
    Both values are identical Win32 `FILETIME` ticks (100-nanosecond intervals since Jan 1, 1601 UTC). Zero unit conversion error.
- **Linux / POSIX Protocol:**
  - Encodes the process start time directly from `/proc/self/stat` field 22 (`starttime` in clock jiffies):
    $$\texttt{m02\_spill\_<pid>\_<jiffies\_u64>\_<uuid>.lock}$$
  - The scavenger inspects `/proc/<pid>/stat` field 22 and performs an exact integer comparison against `jiffies_u64`.

#### Conservative Retention Rule: Retain on Any Uncertainty
1. An orphan `.bin` file is **never** deleted based on elapsed time alone. A long-running ingestion operation or paused debugger could legitimately hold a spill file for arbitrary durations.
2. An orphan `.bin` is eligible for deletion **only if**:
   - The creating PID is affirmatively confirmed dead by the OS kernel (e.g. `OpenProcess` fails with `ERROR_INVALID_PARAMETER` or process creation time mismatch), **AND**
   - An exclusive file open (`CreateFileW` with `FILE_SHARE_NONE` on Windows or `flock(LOCK_EX | LOCK_NB)` on POSIX) succeeds.
3. **Fail-Safe Invariant:** If process query returns `ERROR_ACCESS_DENIED`, or permission is denied, or start time cannot be read conclusively, **the file is retained untouched**.

---

### 1.3 Correction 3: Double-Checked Locking in Concurrent Cache-Miss Handling

To prevent redundant physical disk reads when multiple threads concurrently query the same un-cached string index:

#### Double-Checked Locking Protocol
```
Thread 1..8 (Concurrent Query for Spilled String Index K):
  │
  ├─► 1. Check LRU: Acquire L2 (Mutex<LruArena>)
  │     └─► Index K is cold (cache miss) in all 8 threads
  │
  ├─► 2. Release L2
  │
  ├─► 3. Compete for L1 (Mutex<ScratchSpillFile>)
  │     └─► Thread 1 acquires L1; Threads 2..8 block awaiting L1
  │
  ├─► 4. Double-Check LRU under L1:
  │     └─► Thread 1 acquires L2: Index K is still missing.
  │     └─► Thread 1 performs disk seek & read on spill file.
  │     └─► Thread 1 inserts K into LruArena.
  │     └─► Thread 1 releases L2; releases L1.
  │
  └─► 5. Threads 2..8 unblock sequentially under L1:
        └─► Thread 2 acquires L1.
        └─► Thread 2 acquires L2 and RECHECKS LRU:
              Index K is NOW PRESENT (populated by Thread 1)!
        └─► Thread 2 copies string from LruArena, releases L2, releases L1.
        └─► ZERO disk reads performed by Threads 2..8.
```

#### Verification Test (`test_concurrent_same_index_single_disk_read`)
- Integrates an atomic instrumentation counter `disk_read_count: AtomicUsize` inside the spill file reader.
- 8 concurrent OS threads query the exact same cold index simultaneously.
- **Assertion:** All 8 threads return the verified string; `disk_read_count.load(Ordering::SeqCst) == 1` (exactly one physical disk read executed).

---

## 2. Final Implementation Sequence (Pre-Authorization Status)

```
Step 1: Safe Niche-Optimized LRU Arena (crates/excel_intel_rs/src/shared_strings.rs)
  ├── Implement LruSlot using Option<NonZeroU32> (40 bytes verified).
  ├── Implement Double-Checked Locking (L1 -> L2 recheck protocol).
  └── Add unit test test_concurrent_same_index_single_disk_read.

Step 2: Lock-First Creation & OS-Native Scavenger (crates/excel_intel_rs/src/scratch.rs)
  ├── Lock .lock before creating .bin.
  ├── Implement native GetProcessTimes FILETIME comparison on Windows.
  └── Enforce "retain on uncertainty" rule for orphan .bin files.

Step 3: Memory Guard Telemetry & Dual Cadence (crates/excel_intel_rs/src/memory_guard.rs)
  ├── 1,000-row cadence (~10 ms at 100K rows/sec) + 8.0 MiB event trigger.
  └── 235.0 MiB defensive abort tripwire.

Step 4: Integration Wiring & Concurrency Test Implementation (tests/)
  ├── test_shared_strings_spill.py
  ├── test_scratch_lifecycle.py
  └── test_bounded_memory.py

Step 5: Full Build, Verification & Evidence Report
  ├── cargo test, cargo fmt --check, cargo clippy -- -D warnings.
  ├── pytest across Python 3.12 and 3.13.
  └── Author M02_SPRINT_2_EVIDENCE_REPORT.md and STOP.
```

---

## 3. Governance Declaration

- **Production Code Status:** Zero production code modified.
- **Sprint 1 Status:** Frozen and accepted.
- **STOP Condition:** Pre-implementation planning is complete. Awaiting explicit Project Owner authorization to begin implementation.
