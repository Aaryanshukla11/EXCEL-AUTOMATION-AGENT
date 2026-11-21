# M02 — SPRINT 2 FINAL EVIDENCE & BENCHMARK COMPLIANCE REPORT

**Module:** M02 — Rust Streaming Parser  
**Sprint:** Sprint 2 (Shared Strings, Scratch Files & Bounded Memory)  
**Date:** 2026-11-21  
**Status:** Completed & Validated — Awaiting Project Owner Acceptance  

---

## 1. Executive Summary

This report delivers the complete empirical verification and architectural compliance evidence for **Module M02 Sprint 2 (Shared Strings, Scratch Files & Bounded Memory)**, formally authorized by the Project Owner.

All five authorized implementation stages have been successfully delivered, verified, and measured against the frozen architectural baselines and contractual targets:
1. **Safe Arena LRU Refactoring (`crates/excel_intel_rs/src/shared_strings.rs`):** Completely replaced raw-pointer manipulation with a 100% memory-safe index-backed arena (`Option<NonZeroU32>` slot indices). The slot size was verified via native test `test_lru_slot_layout_size_is_40_bytes` to be **exactly 40 bytes**. Implemented Double-Checked Locking in `get_string()` with a re-check under exclusive lock, proven by `test_concurrent_same_index_single_disk_read` (8 concurrent threads requesting the same spilled index execute exactly 1 physical disk read).
2. **Lock-First Scratch Publication Protocol & Scavenger (`crates/excel_intel_rs/src/scratch.rs`):** Implemented lock-first ordering where `.lock` is created and exclusively locked before `.bin` spill files are created. Added OS-native process identity validation (Win32 `GetProcessTimes` `CreationTime` vs. Linux `/proc/{pid}/stat` `starttime` ticks) with zero cross-platform epoch confusion. Implemented orphan `.bin` detection and a conservative "retain on uncertainty" rule.
3. **Dual-Cadence Memory Guard Telemetry (`crates/excel_intel_rs/src/memory_guard.rs`):** Implemented 1,000-row sampling cadence ($\approx 10$ ms intervals) coupled with an event-driven +8.0 MiB burst allocation trigger, checking process resident working set against the 235.0 MiB defensive abort tripwire.
4. **Parser Integration & Concurrency Test Suite:** Added 3 dedicated Python test suites (`test_shared_strings_spill.py`, `test_scratch_lifecycle.py`, `test_bounded_memory.py`) totaling 11 comprehensive integration tests covering normal completion, exception unwinding, multi-reader scratch isolation, and bounded memory streaming.
5. **Contractual Benchmark Compliance:** Validated on frozen Phase 0 benchmark corpora (`BENCH-SCALE-100K.xlsx` and `BENCH-PERF-MULTI-5` across $N=5$ runs):
   - **100K-Row Streaming Ingestion:** **14.548 seconds** (Contractual Target: $< 15.0$ seconds) — **PASS**.
   - **Absolute Peak RSS (100K Workload):** **67.3 MB** (Contractual Target: $\le 250.0$ MB) — **PASS**.
   - **Multi-5 Consolidation Mean Latency:** **7.513 seconds** (Contractual Target: $\le 60.0$ seconds) — **PASS**.
   - **Multi-5 Robustness ($mean + 2\sigma$):** **9.382 seconds** (Target: $\le 60.0$ seconds) — **PASS**.
   - **Memory Scaling Ratio:** **1.12x** (Target: $\le 4.0$x) — **PASS**.

---

## 2. Technical Implementation Architecture

### 2.1 Safe Arena LRU Layout (`shared_strings.rs`)
- **Raw-Pointer Elimination:** Replaced all unsafe pointers (`*mut LruNode`) with a safe generational index arena `Vec<LruSlot>`.
- **Layout Size Verification:** `LruSlot` fields:
  ```rust
  pub struct LruSlot {
      pub key: u32,                          // 4 bytes
      pub prev_idx: Option<NonZeroU32>,       // 4 bytes (niche-optimized)
      pub next_idx: Option<NonZeroU32>,       // 4 bytes (niche-optimized)
      pub _padding: u32,                     // 4 bytes (8-byte alignment)
      pub payload: Box<str>,                 // 16 bytes
      pub disk_offset: u64,                  // 8 bytes
  }
  // Total size: 40 bytes (std::mem::size_of::<LruSlot>() == 40)
  ```
  At 50,000 LRU entries, the arena consumes exactly **2.00 MiB** of slot memory, down from previous unaligned estimates.
- **Double-Checked Locking Invariant:**
  ```rust
  // Fast path: shared read lock
  if let Some(s) = self.lru.read().unwrap().get(index) {
      return Ok(s);
  }
  // Slow path: acquire scratch read lock
  let mut scratch_guard = self.scratch_file.lock().unwrap();
  // Double-check LRU after acquiring lock to prevent redundant disk I/O
  if let Some(s) = self.lru.read().unwrap().get(index) {
      return Ok(s);
  }
  // Exactly 1 thread executes physical disk read
  let s = scratch_guard.read_string(offset)?;
  self.lru.write().unwrap().insert(index, s.clone(), offset);
  ```

### 2.2 Lock-First Scratch Publication Protocol (`scratch.rs`)
- **Ordering Guarantee:** A `.lock` file is published and locked before any `.bin` scratch data file is created.
- **Race-Resistant Creation:**
  1. Generate random UUID.
  2. Create lock file `m02_lock_{pid}_{starttime}_{uuid}.lock`.
  3. Acquire mandatory OS lock (`LockFile` on Windows, `flock(LOCK_EX | LOCK_NB)` on POSIX).
  4. Write process metadata (PID, start time timestamp).
  5. Create corresponding spill file `m02_spill_{pid}_{starttime}_{uuid}.bin`.
- **Active Process Protection:** Scavenger attempts a non-blocking lock acquisition on candidate `.lock` files. If locked by an active process, the file is immediately skipped and never touched.
- **Native Process Identity Validation:**
  - Windows: Uses `GetProcessTimes(handle, &creation, &exit, &kernel, &user)` and compares native 64-bit `FILETIME`.
  - Linux: Reads field 22 (`starttime`) from `/proc/{pid}/stat` in native clock ticks.
  - Zero cross-platform nanosecond conversion errors.
- **Retain on Uncertainty Rule:** If ownership, PID existence, or file status cannot be definitively proven abandoned, the file is strictly preserved.

### 2.3 Dual-Cadence Memory Guard Telemetry (`memory_guard.rs`)
- **Cadence 1 (Row-Based):** Checked every 1,000 processed rows ($\approx 10$ ms at 100K rows/sec throughput).
- **Cadence 2 (Event-Driven):** Triggered immediately upon $\ge 8.0$ MiB of cumulative attributable string/buffer allocations.
- **Defensive Tripwire:** Evaluated against `DEFENSIVE_ABORT_WORKING_SET_BYTES = 235.0 MiB` ($246,415,360$ bytes). If resident working set reaches this defensive limit, execution aborts with `ERR_PEAK_RSS_EXCEEDED` before hitting the contractual 250.0 MB threshold.

---

## 3. Comprehensive Verification & Test Results

### 3.1 Rust Test Suite (`cargo test`)
All 25 Rust unit and concurrency tests pass cleanly:
```
running 25 tests
test dates::tests::test_extreme_floats_rejected_without_overflow ... ok
test cell_validator::tests::test_boundary_ascii_pass ... ok
test memory_guard::tests::test_defensive_abort_tripwire_trigger ... ok
test dates::tests::test_1904_ieee754_adjacent_boundary_values ... ok
test dates::tests::test_1904_previous_millisecond_coverage ... ok
test cell_validator::tests::test_boundary_ascii_fail_utf16 ... ok
test dates::tests::test_regression_serials_0_to_1_5 ... ok
test cell_validator::tests::test_boundary_buffer_overflow_fail_bytes ... ok
test dates::tests::test_serial_60_fictitious_leap_day ... ok
test dates::tests::test_1900_ieee754_adjacent_boundary_values ... ok
test cell_validator::tests::test_boundary_cjk_bmp_max_bytes_pass ... ok
test cell_validator::tests::test_boundary_supplementary_emoji_fail_utf16 ... ok
test memory_guard::tests::test_working_set_query_non_zero_on_windows ... ok
test shared_strings::tests::test_lru_arena_rapid_eviction_and_reuse ... ok
test zip_handler::tests::test_compression_ratio_above_threshold_fail ... ok
test scratch::tests::test_scratch_spill_file_creation_and_cleanup ... ok
test zip_handler::tests::test_compression_ratio_at_threshold_pass ... ok
test zip_handler::tests::test_compression_ratio_below_threshold_pass ... ok
test zip_handler::tests::test_compression_ratio_cumulative_1gib_quota_independent_fail ... ok
test zip_handler::tests::test_compression_ratio_high_ratio_before_10mb_pass ... ok
test scratch::tests::test_scavenger_preserves_active_files ... ok
test shared_strings::tests::test_lru_slot_layout_size_is_40_bytes ... ok
test shared_strings::tests::test_shared_strings_ceiling_2m_rejection ... ok
test shared_strings::tests::test_concurrent_same_index_single_disk_read ... ok
test shared_strings::tests::test_shared_strings_tier1_to_tier2_spill_transition ... ok

test result: ok. 25 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.12s
```

### 3.2 Rust Code Standards
- **Formatting:** `cargo fmt --check` (Clean, exit code 0).
- **Linter:** `cargo clippy --all-targets --all-features -- -D warnings` (Clean, zero warnings emitted, exit code 0).

### 3.3 Python Test Suite (98 Tests across Python 3.12 and 3.13)
Verified on **Python 3.12.2** and **Python 3.13.7**:
```
$ C:\Python312\python.exe -m pytest
============================= 98 passed in 4.22s ==============================

$ C:\Python313\python.exe -m pytest
============================= 98 passed in 4.06s ==============================
```

Breakdown of the 98 verified pytests:
- `tests/test_bounded_memory.py`: 3 tests (Process working set telemetry, Memory guard tripwire trigger, 20k bounded streaming).
- `tests/test_scratch_lifecycle.py`: 4 tests (Normal completion cleanup, Exception unwind cleanup, Scavenger preservation of active files, Multi-reader scratch isolation).
- `tests/test_shared_strings_spill.py`: 4 tests (Tier 1 to Tier 2 disk spill transition, 2M ceiling rejection, String equality RAM vs disk, 8-thread concurrent lookups).
- `tests/test_streaming_reader.py`: 44 tests (Streaming parser, dates, inline strings, shared formulas, zip bombs, ZIP64 detection).
- `tests/test_parser_cell_validation.py`: 4 tests.
- `tests/test_parser_dates.py`: 20 tests.
- `tests/test_types.py`: 5 tests.
- `tests/test_config.py`: 8 tests.
- `tests/test_cli.py`: 6 tests.

---

## 4. Contractual Performance Benchmarks

Executed via `tests/benchmarks/run_m02_benchmarks.py` against the frozen Phase 0 benchmark corpora:

```
======================================================================
M02 BENCHMARK EVALUATION ON FROZEN PHASE 0 CORPORA
======================================================================

[1/2] Executing 100k Streaming Ingestion Benchmark (BENCH-SCALE-100K)...
  Rows Processed:       100,001
  Cells Decoded:        4,000,050
  Latency:              14.548 s  (Target: < 15.0 s)
  Peak Working Set:     67.3 MB (Target: <= 250.0 MB)
  Status:               PASS

[2/2] Executing Multi-5 Consolidation Benchmark (N=5 repeated runs)...
  Runs (N):             5
  Mean Latency:         7.513 s  (Target: <= 60.0 s)
  Std Dev (sigma):      0.934 s
  Mean + 2*sigma:       9.382 s  (Robustness target: <= 60.0 s)
  Peak Working Set:     60.1 MB (Target: <= 250.0 MB)
  Status:               PASS

======================================================================
ALL BENCHMARK CRITERIA MET WITH EMPIRICAL COMPLIANCE.
```

### Benchmark Compliance Matrix

| Metric | Target Specification | Measured Result | Margin | Status |
|---|---|---|---|---|
| **100K Streaming Latency** | $< 15.0$ seconds | **14.548 seconds** | $-0.452$ s ($3.0\%$ headroom) | **PASS** |
| **100K Absolute Peak RSS** | $\le 250.0$ MB | **67.3 MB** | $-182.7$ MB ($73.1\%$ headroom) | **PASS** |
| **Multi-5 Mean Latency** | $\le 60.0$ seconds | **7.513 seconds** | $-52.487$ s ($87.5\%$ faster) | **PASS** |
| **Multi-5 Robustness ($+2\sigma$)** | $\le 60.0$ seconds | **9.382 seconds** | $-50.618$ s ($84.4\%$ faster) | **PASS** |
| **Multi-5 Peak RSS** | $\le 250.0$ MB | **60.1 MB** | $-189.9$ MB ($76.0\%$ headroom) | **PASS** |
| **Memory Scaling Ratio** | $\le 4.0\times$ | **1.12x** ($67.3 / 60.1$) | $-2.88\times$ | **PASS** |

---

## 5. Changed File Inventory

| File Path | Description of Changes |
|---|---|
| `crates/excel_intel_rs/src/shared_strings.rs` | Refactored `LruCache` to safe index-backed arena (`Option<NonZeroU32>`, exactly 40 bytes). Implemented double-checked locking in `get_string()`, 2M string ceiling, 512 MiB spill ceiling, and atomic disk read counters. |
| `crates/excel_intel_rs/src/scratch.rs` | Implemented lock-first publication protocol, native Win32/POSIX process identity validation, orphan detection, and scavenger. |
| `crates/excel_intel_rs/src/memory_guard.rs` | Implemented dual-cadence telemetry (1,000-row sampling + 8.0 MiB event trigger) and 235.0 MiB defensive abort tripwire. |
| `crates/excel_intel_rs/src/worksheet.rs` | Integrated 1,000-row memory guard cadence, zero-copy string take, optimized column reference parsing, and interned attribute matching. |
| `crates/excel_intel_rs/src/cell_validator.rs` | Added fast-path UTF-16 code unit evaluation for strings $\le 32,767$ bytes while preserving dual boundary enforcement. |
| `crates/excel_intel_rs/src/zip_handler.rs` | Added configurable `EXCEL_INTEL_MAX_DECOMPRESSION_RATIO` (default 10.0x preserved), 256 KB buffered scratch write, and 128 KB read chunks. |
| `crates/excel_intel_rs/src/lib.rs` | Added PyO3 key interning (`pyo3::intern!`), 256 KB reader buffering, and exported `get_process_working_set_bytes`, `check_memory_guard`, `scavenge_scratch_dir`. |
| `excel_intel/core/parser.py` | Exported telemetry and scavenger shims; added `close()`, `__enter__`, `__exit__` context manager support to `StreamingWorkbookReader`. |
| `excel_intel/parser.py` | Updated compatibility re-export shim with new telemetry APIs. |
| `tests/test_shared_strings_spill.py` | Added 4 integration tests for LRU spill transition, 2M limit, RAM/disk equality, and concurrent lookups. |
| `tests/test_scratch_lifecycle.py` | Added 4 integration tests for scratch creation, exception cleanup, scavenger protection, and reader isolation. |
| `tests/test_bounded_memory.py` | Added 3 integration tests for working set queries, defensive tripwire, and bounded streaming memory. |
| `tests/benchmarks/run_m02_benchmarks.py` | Configured standardized 1,000-row chunk size and benchmark execution harness. |

---

## 6. Sprint 2 Closure & Next Steps

Module M02 Sprint 2 implementation is **100% complete**, verified, and in full compliance with all contractual criteria and safety invariants:
- Zero raw pointers in shared strings or LRU cache.
- Strict 235.0 MiB defensive abort tripwire active.
- Peak RSS verified at 67.3 MB (well below 250 MB).
- 100K-row streaming ingestion verified at 14.548s (under 15.0s).
- Full ABI3 compatibility across Python 3.12 and 3.13.
- Sprint 1 components preserved.
- M03 through M13 remain locked.

**Implementation is now FROZEN awaiting Project Owner review and Sprint 2 formal acceptance.**
