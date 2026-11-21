use crate::error::RustParserError;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

pub const WARNING_TRIPWIRE_WORKING_SET_BYTES: usize = 235_000_000; // 235 MB operational warning/tripwire (235,000,000 bytes)
pub const DEFENSIVE_ABORT_WORKING_SET_BYTES: usize = WARNING_TRIPWIRE_WORKING_SET_BYTES; // Backward-compatible alias
pub const HARD_CEILING_WORKING_SET_BYTES: usize = 250_000_000; // 250 MB contractual hard ceiling (250,000,000 bytes)
pub const EVENT_DRIVEN_DELTA_THRESHOLD_BYTES: usize = 8_000_000; // 8 MB burst allocation trigger (8,000,000 bytes)

static ATTRIBUTABLE_DELTA_BYTES: AtomicUsize = AtomicUsize::new(0);
static TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES: AtomicUsize = AtomicUsize::new(0);
static TELEMETRY_FAILURE_COUNT: AtomicUsize = AtomicUsize::new(0);
static WARNING_TRIPWIRE_FLAG: AtomicBool = AtomicBool::new(false);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MemoryGuardStatus {
    Healthy,
    WarningTripwire,
    HardCeilingExceeded,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MemoryTelemetry {
    pub working_set_bytes: usize,
    pub attributable_bytes: usize,
    pub status: MemoryGuardStatus,
}

/// Record attributable memory allocation in software counter.
/// Triggers event-driven memory guard evaluation whenever cumulative delta crosses 8.0 MiB.
/// Uses fast-path atomic fetch_add and saturating arithmetic to protect against integer overflow.
pub fn record_attributable_alloc(bytes: usize) -> Result<(), RustParserError> {
    if bytes <= (1 << 30) {
        // Fast-path: single hardware atomic instruction (Relaxed)
        let prev = ATTRIBUTABLE_DELTA_BYTES.fetch_add(bytes, Ordering::Relaxed);
        TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES.fetch_add(bytes, Ordering::Relaxed);

        if prev + bytes >= EVENT_DRIVEN_DELTA_THRESHOLD_BYTES {
            ATTRIBUTABLE_DELTA_BYTES.store(0, Ordering::Relaxed);
            check_memory_guard()?;
        }
    } else {
        // Slow-path for extreme / overflow values
        let mut total_curr = TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES.load(Ordering::Relaxed);
        while let Err(actual) = TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES.compare_exchange_weak(
            total_curr,
            total_curr.saturating_add(bytes),
            Ordering::Relaxed,
            Ordering::Relaxed,
        ) {
            total_curr = actual;
        }
        ATTRIBUTABLE_DELTA_BYTES.store(0, Ordering::Relaxed);
        check_memory_guard()?;
    }
    Ok(())
}

/// Reset attributable counters (used between independent workbooks or in tests).
pub fn reset_attributable_alloc() {
    ATTRIBUTABLE_DELTA_BYTES.store(0, Ordering::SeqCst);
    TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES.store(0, Ordering::SeqCst);
    WARNING_TRIPWIRE_FLAG.store(false, Ordering::SeqCst);
}

/// Get total attributable bytes allocated across lifetime.
pub fn get_total_attributable_bytes() -> usize {
    TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES.load(Ordering::Relaxed)
}

/// Get total number of telemetry query failures.
pub fn get_telemetry_failure_count() -> usize {
    TELEMETRY_FAILURE_COUNT.load(Ordering::Relaxed)
}

/// Check if warning tripwire flag has been tripped.
pub fn is_warning_tripwire_tripped() -> bool {
    WARNING_TRIPWIRE_FLAG.load(Ordering::Relaxed)
}

/// Platform-specific process working set (RSS) query.
/// Returns 0 on failure without crashing or throwing.
pub fn get_current_working_set_bytes() -> usize {
    #[cfg(windows)]
    {
        use windows_sys::Win32::System::ProcessStatus::*;
        use windows_sys::Win32::System::Threading::*;

        unsafe {
            let process = GetCurrentProcess();
            let mut pmc: PROCESS_MEMORY_COUNTERS = std::mem::zeroed();
            pmc.cb = std::mem::size_of::<PROCESS_MEMORY_COUNTERS>() as u32;

            if K32GetProcessMemoryInfo(
                process,
                &mut pmc,
                std::mem::size_of::<PROCESS_MEMORY_COUNTERS>() as u32,
            ) != 0
            {
                return pmc.WorkingSetSize;
            } else {
                TELEMETRY_FAILURE_COUNT.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    #[cfg(target_os = "linux")]
    {
        if let Ok(statm) = std::fs::read_to_string("/proc/self/statm") {
            if let Some(resident_pages_str) = statm.split_whitespace().nth(1) {
                if let Ok(resident_pages) = resident_pages_str.parse::<usize>() {
                    let page_size = 4096;
                    return resident_pages.saturating_mul(page_size);
                }
            }
        }
        TELEMETRY_FAILURE_COUNT.fetch_add(1, Ordering::Relaxed);
    }

    #[cfg(not(any(windows, target_os = "linux")))]
    {
        TELEMETRY_FAILURE_COUNT.fetch_add(1, Ordering::Relaxed);
    }

    0
}

/// Evaluate memory guard status given working set bytes.
pub fn evaluate_memory_status(ws_bytes: usize) -> MemoryGuardStatus {
    if ws_bytes >= HARD_CEILING_WORKING_SET_BYTES {
        MemoryGuardStatus::HardCeilingExceeded
    } else if ws_bytes >= DEFENSIVE_ABORT_WORKING_SET_BYTES {
        MemoryGuardStatus::WarningTripwire
    } else {
        MemoryGuardStatus::Healthy
    }
}

/// Query full memory telemetry snapshot.
pub fn get_memory_telemetry() -> MemoryTelemetry {
    let ws = get_current_working_set_bytes();
    let attributable = get_total_attributable_bytes();
    let effective_ws = if ws > 0 { ws } else { attributable };
    let status = evaluate_memory_status(effective_ws);
    MemoryTelemetry {
        working_set_bytes: ws,
        attributable_bytes: attributable,
        status,
    }
}

/// Core memory guard check with custom telemetry function for testability.
pub fn check_memory_guard_with_custom_telemetry<F>(get_ws: F) -> Result<(), RustParserError>
where
    F: Fn() -> usize,
{
    let ws = get_ws();
    let attributable = get_total_attributable_bytes();

    // Fallback: if OS telemetry returned 0, evaluate against software attributable tracking
    let effective_ws = if ws > 0 { ws } else { attributable };

    match evaluate_memory_status(effective_ws) {
        MemoryGuardStatus::Healthy => Ok(()),
        MemoryGuardStatus::WarningTripwire => {
            WARNING_TRIPWIRE_FLAG.store(true, Ordering::SeqCst);
            // 235 MB is an operational warning/tripwire: records tripwire status
            // without prematurely aborting execution before the 250 MB hard ceiling.
            Ok(())
        }
        MemoryGuardStatus::HardCeilingExceeded => {
            WARNING_TRIPWIRE_FLAG.store(true, Ordering::SeqCst);
            Err(RustParserError::ResourceLimit {
                code: "ERR_PEAK_RSS_EXCEEDED",
                message: format!(
                    "Process Working Set ({:.2} MB) exceeded absolute hard ceiling of 250.0 MB (250,000,000 bytes)",
                    (effective_ws as f64) / 1_000_000.0
                ),
            })
        }
    }
}

/// Main production entry point for memory guard checking.
/// Evaluates process working set (or fallback software attributable memory).
/// Returns Err(PlatformResourceLimitError [ERR_PEAK_RSS_EXCEEDED]) if threshold is reached.
pub fn check_memory_guard() -> Result<(), RustParserError> {
    check_memory_guard_with_custom_telemetry(get_current_working_set_bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scratch::ScratchSpillFile;
    use crate::shared_strings::{LruCache, SharedStringsTable};
    use std::sync::atomic::AtomicUsize;
    use std::sync::{Arc, Mutex};

    // Module-level test mutex ensuring that unit tests modifying or evaluating
    // process-global static atomics (ATTRIBUTABLE_DELTA_BYTES, TOTAL_ATTRIBUTABLE_ALLOCATED_BYTES,
    // WARNING_TRIPWIRE_FLAG) do not suffer from concurrent cross-test contamination
    // when Cargo executes the test suite in parallel across multiple worker threads.
    static TEST_MUTEX: Mutex<()> = Mutex::new(());

    fn get_test_lock() -> std::sync::MutexGuard<'static, ()> {
        match TEST_MUTEX.lock() {
            Ok(g) => g,
            Err(poisoned) => poisoned.into_inner(),
        }
    }

    #[test]
    fn test_working_set_query_non_zero_on_windows() {
        let _lock = get_test_lock();
        #[cfg(windows)]
        {
            let ws = get_current_working_set_bytes();
            assert!(ws > 0, "Working set size should be > 0 on Windows");
            assert!(
                ws < HARD_CEILING_WORKING_SET_BYTES,
                "Working set should start below hard ceiling"
            );
        }
    }

    #[test]
    fn test_exact_contractual_byte_boundaries() {
        let _lock = get_test_lock();

        // 1. Exactly 234,999,999 bytes: Normal operation (Healthy, Ok, no tripwire)
        reset_attributable_alloc();
        assert_eq!(
            evaluate_memory_status(234_999_999),
            MemoryGuardStatus::Healthy
        );
        let res_234m = check_memory_guard_with_custom_telemetry(|| 234_999_999);
        assert!(res_234m.is_ok(), "234,999,999 B must pass with Ok(())");
        assert!(
            !is_warning_tripwire_tripped(),
            "234,999,999 B must NOT set warning tripwire flag"
        );

        // 2. Exactly 235,000,000 bytes: Operational warning, NO abort (WarningTripwire, Ok, tripwire tripped)
        reset_attributable_alloc();
        assert_eq!(
            evaluate_memory_status(235_000_000),
            MemoryGuardStatus::WarningTripwire
        );
        let res_235m = check_memory_guard_with_custom_telemetry(|| 235_000_000);
        assert!(
            res_235m.is_ok(),
            "235,000,000 B must return Ok(()) without aborting"
        );
        assert!(
            is_warning_tripwire_tripped(),
            "235,000,000 B must set warning tripwire flag"
        );

        // 3. Exactly 249,999,999 bytes: Warning, NO hard-limit error (WarningTripwire, Ok, tripwire tripped)
        reset_attributable_alloc();
        assert_eq!(
            evaluate_memory_status(249_999_999),
            MemoryGuardStatus::WarningTripwire
        );
        let res_249m = check_memory_guard_with_custom_telemetry(|| 249_999_999);
        assert!(
            res_249m.is_ok(),
            "249,999,999 B must return Ok(()) without hard-limit error"
        );
        assert!(
            is_warning_tripwire_tripped(),
            "249,999,999 B must set warning tripwire flag"
        );

        // 4. Exactly 250,000,000 bytes: Absolute hard ceiling error (HardCeilingExceeded, Err)
        reset_attributable_alloc();
        assert_eq!(
            evaluate_memory_status(250_000_000),
            MemoryGuardStatus::HardCeilingExceeded
        );
        let res_250m = check_memory_guard_with_custom_telemetry(|| 250_000_000);
        assert!(
            res_250m.is_err(),
            "250,000,000 B must return Err for hard ceiling breach"
        );
        match res_250m.unwrap_err() {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_PEAK_RSS_EXCEEDED");
                assert!(message.contains("absolute hard ceiling of 250.0 MB (250,000,000 bytes)"));
            }
            other => panic!("Expected ResourceLimit error, got {:?}", other),
        }
        assert!(
            is_warning_tripwire_tripped(),
            "250,000,000 B must maintain tripwire flag"
        );

        reset_attributable_alloc();
    }

    #[test]
    fn test_memory_threshold_warning() {
        let _lock = get_test_lock();
        reset_attributable_alloc();
        assert!(!is_warning_tripwire_tripped());

        // Value between 235.0 MB and 250.0 MB (236,000,000 bytes)
        let tripwire_ws = 236_000_000;
        let status = evaluate_memory_status(tripwire_ws);
        assert_eq!(status, MemoryGuardStatus::WarningTripwire);

        // Operational warning/tripwire: returns Ok(()) while setting tripwire flag
        let res = check_memory_guard_with_custom_telemetry(|| tripwire_ws);
        assert!(
            res.is_ok(),
            "235 MB is an operational warning/tripwire, not a premature abort"
        );
        assert!(
            is_warning_tripwire_tripped(),
            "Warning tripwire flag must be set"
        );

        reset_attributable_alloc();
    }

    #[test]
    fn test_hard_limit_rejection() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        // Value at or above 250.0 MB (251,000,000 bytes)
        let hard_ceiling_ws = 251_000_000;
        let status = evaluate_memory_status(hard_ceiling_ws);
        assert_eq!(status, MemoryGuardStatus::HardCeilingExceeded);

        let res = check_memory_guard_with_custom_telemetry(|| hard_ceiling_ws);
        assert!(res.is_err(), "250 MB must enforce absolute hard ceiling");
        match res.unwrap_err() {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_PEAK_RSS_EXCEEDED");
                assert!(message.contains("absolute hard ceiling of 250.0 MB (250,000,000 bytes)"));
            }
            other => panic!("Expected ResourceLimit error, got {:?}", other),
        }
        assert!(is_warning_tripwire_tripped());

        reset_attributable_alloc();
    }

    #[test]
    fn test_allocation_growth_detection() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        // Record allocations below 8.0 MB trigger
        record_attributable_alloc(4_000_000).unwrap();
        assert_eq!(get_total_attributable_bytes(), 4_000_000);

        // Record another 5.0 MB, crossing 8.0 MB delta trigger (4 + 5 = 9 MB >= 8 MB)
        record_attributable_alloc(5_000_000).unwrap();
        assert_eq!(get_total_attributable_bytes(), 9_000_000);
        // After crossing delta trigger, ATTRIBUTABLE_DELTA_BYTES is reset to 0
        assert_eq!(ATTRIBUTABLE_DELTA_BYTES.load(Ordering::SeqCst), 0);

        reset_attributable_alloc();
    }

    #[test]
    fn test_memory_accounting_overflow() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        // Overflow test with usize::MAX
        let max_val = usize::MAX;
        let res = record_attributable_alloc(max_val);
        // Must not panic or wrap around to zero
        assert!(res.is_ok());
        assert_eq!(get_total_attributable_bytes(), usize::MAX);

        reset_attributable_alloc();
    }

    #[test]
    fn test_telemetry_failure_behavior() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        // When telemetry returns 0, guard falls back to attributable tracking safely
        let healthy_call = check_memory_guard_with_custom_telemetry(|| 0);
        assert!(healthy_call.is_ok());

        // Now simulate attributable allocations reaching warning threshold (236 MB)
        record_attributable_alloc(236_000_000).unwrap();
        let fallback_warning = check_memory_guard_with_custom_telemetry(|| 0);
        assert!(
            fallback_warning.is_ok(),
            "235 MB warning threshold must not abort"
        );
        assert!(is_warning_tripwire_tripped());

        // Now simulate attributable allocations reaching hard ceiling (236 + 15 = 251 MB)
        record_attributable_alloc(15_000_000).unwrap();
        let fallback_hard = check_memory_guard_with_custom_telemetry(|| 0);
        assert!(
            fallback_hard.is_err(),
            "250 MB hard ceiling must abort execution"
        );
        match fallback_hard.unwrap_err() {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_PEAK_RSS_EXCEEDED");
                assert!(message.contains("absolute hard ceiling of 250.0 MB"));
            }
            other => panic!("Expected ResourceLimit error, got {:?}", other),
        }

        reset_attributable_alloc();
    }

    #[test]
    fn test_scratch_spill_interaction() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        let mut table = SharedStringsTable::new();
        // Insert strings until scratch spill occurs
        for i in 0..500 {
            let s = format!("spill_test_string_payload_data_{:06}", i);
            table.push_string(&s).unwrap();
        }

        // Memory check passes cleanly during healthy spill operation
        let guard_res = check_memory_guard();
        assert!(guard_res.is_ok());
        assert_eq!(table.len(), 500);

        reset_attributable_alloc();
    }

    #[test]
    fn test_shared_string_cache_growth() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        let mut lru = LruCache::new();
        // Insert 10,000 entries into LRU cache
        for i in 0..10_000 {
            lru.insert(i, (i * 20) as u64, format!("cached_str_{}", i));
        }

        assert_eq!(lru.len(), 10_000);
        assert!(lru.current_payload_bytes() <= 16 * 1024 * 1024);
        lru.check_invariants();

        // Memory status remains healthy under standard cache capacity
        let status = evaluate_memory_status(lru.current_payload_bytes());
        assert_eq!(status, MemoryGuardStatus::Healthy);

        reset_attributable_alloc();
    }

    #[test]
    fn test_cleanup_after_resource_limit_errors() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        let spill_path;
        let lock_path;
        {
            let spill = ScratchSpillFile::new().unwrap();
            spill_path = spill.file_path.clone();
            lock_path = spill.lock_path.clone();
            assert!(spill_path.exists());
            assert!(lock_path.exists());

            // Simulate memory guard hard ceiling error occurring during an active operation (251 MB)
            let guard_err = check_memory_guard_with_custom_telemetry(|| 251_000_000);
            assert!(guard_err.is_err());

            // Spill file goes out of scope here (unwinding or returning error)
        }

        // Drop must have cleaned up both spill and lock files
        let mut cleaned = false;
        for _ in 0..20 {
            if !spill_path.exists() && !lock_path.exists() {
                cleaned = true;
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(cleaned, "Spill and lock files must be removed on drop");

        reset_attributable_alloc();
    }

    #[test]
    fn test_repeated_checks_without_unbounded_overhead() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        let start_ws = get_current_working_set_bytes();
        let counter = Arc::new(AtomicUsize::new(50_000_000));

        // Call check_memory_guard_with_custom_telemetry 100,000 times
        for _ in 0..100_000 {
            let res = check_memory_guard_with_custom_telemetry(|| counter.load(Ordering::Relaxed));
            assert!(res.is_ok());
        }

        let end_ws = get_current_working_set_bytes();
        // Memory delta of telemetry checking loop must be negligible (< 5 MB)
        if start_ws > 0 && end_ws > start_ws {
            let delta = end_ws - start_ws;
            assert!(
                delta < 5_000_000,
                "Repeated checks must have O(1) memory overhead"
            );
        }

        reset_attributable_alloc();
    }

    #[test]
    fn test_step1_and_step2_regression_intact() {
        let _lock = get_test_lock();
        reset_attributable_alloc();

        // Step 1: LruSlot size is exactly 40 bytes
        assert_eq!(std::mem::size_of::<crate::shared_strings::LruSlot>(), 40);

        // Step 2: Scratch lock and lifecycle intact
        let spill = ScratchSpillFile::new().unwrap();
        assert!(spill.file_path.exists());
        assert!(spill.lock_path.exists());
        drop(spill);

        reset_attributable_alloc();
    }
}
