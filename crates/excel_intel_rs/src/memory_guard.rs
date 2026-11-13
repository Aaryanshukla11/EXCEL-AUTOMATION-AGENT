use crate::error::RustParserError;

pub const DEFENSIVE_ABORT_WORKING_SET_BYTES: usize = 235 * 1024 * 1024; // 235.0 MB

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

    0
}

pub fn check_memory_guard() -> Result<(), RustParserError> {
    let ws = get_current_working_set_bytes();
    if ws >= DEFENSIVE_ABORT_WORKING_SET_BYTES {
        return Err(RustParserError::ResourceLimit {
            code: "ERR_PEAK_RSS_EXCEEDED",
            message: format!(
                "Process Working Set ({} MB) exceeded defensive tripwire threshold of 235.0 MB",
                ws / (1024 * 1024)
            ),
        });
    }
    Ok(())
}
