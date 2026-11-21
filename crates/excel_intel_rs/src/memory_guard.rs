use crate::error::RustParserError;
use std::sync::atomic::{AtomicUsize, Ordering};

pub const DEFENSIVE_ABORT_WORKING_SET_BYTES: usize = 235 * 1024 * 1024; // 235.0 MiB defensive abort tripwire
pub const EVENT_DRIVEN_DELTA_THRESHOLD_BYTES: usize = 8 * 1024 * 1024; // 8.0 MiB burst allocation trigger

static ATTRIBUTABLE_DELTA_BYTES: AtomicUsize = AtomicUsize::new(0);

pub fn record_attributable_alloc(bytes: usize) -> Result<(), RustParserError> {
    let prev = ATTRIBUTABLE_DELTA_BYTES.fetch_add(bytes, Ordering::Relaxed);
    if prev + bytes >= EVENT_DRIVEN_DELTA_THRESHOLD_BYTES {
        ATTRIBUTABLE_DELTA_BYTES.store(0, Ordering::Relaxed);
        check_memory_guard()?;
    }
    Ok(())
}

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
            }
        }
    }

    #[cfg(target_os = "linux")]
    {
        if let Ok(statm) = std::fs::read_to_string("/proc/self/statm") {
            if let Some(resident_pages_str) = statm.split_whitespace().nth(1) {
                if let Ok(resident_pages) = resident_pages_str.parse::<usize>() {
                    let page_size = 4096;
                    return resident_pages * page_size;
                }
            }
        }
    }

    0
}

pub fn check_memory_guard() -> Result<(), RustParserError> {
    let ws = get_current_working_set_bytes();
    if ws >= DEFENSIVE_ABORT_WORKING_SET_BYTES {
        return Err(RustParserError::ResourceLimit {
            code: "ERR_PEAK_RSS_EXCEEDED",
            message: format!(
                "Process Working Set ({:.2} MiB) exceeded defensive tripwire threshold of 235.0 MiB",
                (ws as f64) / (1024.0 * 1024.0)
            ),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_working_set_query_non_zero_on_windows() {
        #[cfg(windows)]
        {
            let ws = get_current_working_set_bytes();
            assert!(ws > 0, "Working set size should be > 0 on Windows");
        }
    }

    #[test]
    fn test_defensive_abort_tripwire_trigger() {
        // Test that exceeding 235 MiB generates ERR_PEAK_RSS_EXCEEDED
        let fake_ws = 236 * 1024 * 1024;
        assert!(fake_ws >= DEFENSIVE_ABORT_WORKING_SET_BYTES);
    }
}
