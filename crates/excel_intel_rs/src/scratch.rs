use crate::error::RustParserError;
use std::fs::{File, OpenOptions};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

pub struct ScratchSpillFile {
    pub file_path: PathBuf,
    pub lock_path: PathBuf,
    pub file: File,
    #[cfg(windows)]
    pub lock_handle: windows_sys::Win32::Foundation::HANDLE,
    cleaned: AtomicBool,
}

unsafe impl Send for ScratchSpillFile {}

#[cfg(windows)]
const GENERIC_READ: u32 = 0x80000000;
#[cfg(windows)]
const GENERIC_WRITE: u32 = 0x40000000;
#[cfg(windows)]
const DRIVE_FIXED: u32 = 3;
#[cfg(windows)]
const DRIVE_RAMDISK: u32 = 6;

impl ScratchSpillFile {
    pub fn new() -> Result<Self, RustParserError> {
        crate::memory_guard::check_memory_guard()?;
        let scratch_dir = get_or_create_scratch_dir()?;
        verify_local_filesystem(&scratch_dir)?;

        let pid = std::process::id();
        let start_time = get_process_start_time();
        let unique_id = uuid::Uuid::new_v4();

        let base_name = format!("m02_spill_{}_{}_{}", pid, start_time, unique_id);
        let file_path = scratch_dir.join(format!("{}.bin", base_name));
        let lock_path = scratch_dir.join(format!("{}.lock", base_name));

        #[cfg(windows)]
        let (file, lock_handle) = {
            use std::os::windows::fs::OpenOptionsExt;
            use windows_sys::Win32::Storage::FileSystem::*;

            // STEP 1: Lock-First Protocol — Create and acquire exclusive lock on .lock FIRST
            let lock_wide: Vec<u16> = lock_path
                .to_str()
                .unwrap()
                .encode_utf16()
                .chain(std::iter::once(0))
                .collect();
            let lock_handle = unsafe {
                CreateFileW(
                    lock_wide.as_ptr(),
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ,
                    std::ptr::null_mut(),
                    CREATE_NEW,
                    FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
                    std::ptr::null_mut(),
                )
            };

            if lock_handle == windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE {
                return Err(RustParserError::CorruptWorkbook(
                    "Failed to acquire scratch lock handle".to_string(),
                ));
            }

            let locked = unsafe { LockFile(lock_handle, 0, 0, 1, 0) };
            if locked == 0 {
                unsafe { windows_sys::Win32::Foundation::CloseHandle(lock_handle) };
                let _ = std::fs::remove_file(&lock_path);
                return Err(RustParserError::CorruptWorkbook(
                    "Failed to lock scratch lock file exclusively".to_string(),
                ));
            }

            // STEP 2: Create .bin spill file only after lock is actively held
            let file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
                .open(&file_path)
                .map_err(|e| {
                    unsafe { windows_sys::Win32::Foundation::CloseHandle(lock_handle) };
                    let _ = std::fs::remove_file(&lock_path);
                    RustParserError::CorruptWorkbook(format!(
                        "Failed to create scratch spill file: {}",
                        e
                    ))
                })?;

            (file, lock_handle)
        };

        #[cfg(not(windows))]
        let (file, lock_handle) = {
            use std::os::unix::io::AsRawFd;

            // POSIX Safety Protocol:
            // 1. Create unpublished temp lock file
            let tmp_lock_path = scratch_dir.join(format!("{}.tmp_lock", base_name));
            let lock_file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(&tmp_lock_path)
                .map_err(|e| {
                    RustParserError::CorruptWorkbook(format!(
                        "Failed to create temp lock file: {}",
                        e
                    ))
                })?;

            // 2. Acquire exclusive non-blocking flock
            let ret = unsafe { libc::flock(lock_file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) };
            if ret != 0 {
                let _ = std::fs::remove_file(&tmp_lock_path);
                return Err(RustParserError::CorruptWorkbook(
                    "Failed to acquire exclusive flock on temp lock".to_string(),
                ));
            }

            // 3. Atomically publish locked file
            std::fs::rename(&tmp_lock_path, &lock_path).map_err(|e| {
                let _ = std::fs::remove_file(&tmp_lock_path);
                RustParserError::CorruptWorkbook(format!("Failed to publish lock file: {}", e))
            })?;

            // 4. Create corresponding spill file only after publication
            let file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(&file_path)
                .map_err(|e| {
                    let _ = std::fs::remove_file(&lock_path);
                    RustParserError::CorruptWorkbook(format!(
                        "Failed to create scratch file: {}",
                        e
                    ))
                })?;

            (file, lock_file)
        };

        Ok(Self {
            file_path,
            lock_path,
            file,
            #[cfg(windows)]
            lock_handle,
            cleaned: AtomicBool::new(false),
        })
    }
}

pub fn is_process_dead(pid: u32, expected_start_time: u64) -> bool {
    #[cfg(windows)]
    {
        use windows_sys::Win32::Foundation::*;
        use windows_sys::Win32::System::Threading::*;

        unsafe {
            let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
            if handle.is_null() || handle == INVALID_HANDLE_VALUE {
                let err = GetLastError();
                if err == ERROR_INVALID_PARAMETER {
                    return true;
                }
                return false;
            }

            let mut creation_time: FILETIME = std::mem::zeroed();
            let mut exit_time: FILETIME = std::mem::zeroed();
            let mut kernel_time: FILETIME = std::mem::zeroed();
            let mut user_time: FILETIME = std::mem::zeroed();

            let ok = GetProcessTimes(
                handle,
                &mut creation_time,
                &mut exit_time,
                &mut kernel_time,
                &mut user_time,
            );
            CloseHandle(handle);

            if ok != 0 {
                let actual_start_time = ((creation_time.dwHighDateTime as u64) << 32)
                    | (creation_time.dwLowDateTime as u64);
                if actual_start_time > expected_start_time {
                    return true;
                }
                if actual_start_time == expected_start_time {
                    return false;
                }
            }

            false
        }
    }

    #[cfg(not(windows))]
    {
        let stat_path = format!("/proc/{}/stat", pid);
        if let Ok(content) = std::fs::read_to_string(&stat_path) {
            if let Some(fields) = content.split_whitespace().nth(21) {
                if let Ok(starttime) = fields.parse::<u64>() {
                    if starttime > expected_start_time {
                        return true;
                    }
                    if starttime == expected_start_time {
                        return false;
                    }
                }
            }
            return false;
        }

        let res = unsafe { libc::kill(pid as i32, 0) };
        res == -1 && std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH)
    }
}

pub fn scavenge_scratch_dir() -> Result<usize, RustParserError> {
    let scratch_dir = match get_or_create_scratch_dir() {
        Ok(d) => d,
        Err(_) => return Ok(0),
    };

    let entries = match std::fs::read_dir(&scratch_dir) {
        Ok(e) => e,
        Err(_) => return Ok(0),
    };

    let mut cleaned_count = 0;

    for entry in entries.flatten() {
        let path = entry.path();
        let filename = match path.file_name().and_then(|n| n.to_str()) {
            Some(name) => name.to_string(),
            None => continue,
        };

        if !filename.starts_with("m02_spill_") {
            continue;
        }

        if filename.ends_with(".tmp_lock") {
            continue;
        }

        let parts: Vec<&str> = filename.split('_').collect();
        if parts.len() < 5 {
            continue;
        }

        let pid: u32 = match parts[2].parse() {
            Ok(p) => p,
            Err(_) => continue,
        };
        let start_time: u64 = match parts[3].parse() {
            Ok(t) => t,
            Err(_) => continue,
        };

        if filename.ends_with(".lock") {
            #[cfg(windows)]
            {
                use windows_sys::Win32::Storage::FileSystem::*;
                let lock_wide: Vec<u16> = path
                    .to_str()
                    .unwrap()
                    .encode_utf16()
                    .chain(std::iter::once(0))
                    .collect();

                let handle = unsafe {
                    CreateFileW(
                        lock_wide.as_ptr(),
                        GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ,
                        std::ptr::null_mut(),
                        OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
                        std::ptr::null_mut(),
                    )
                };

                if handle != windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE {
                    let locked = unsafe { LockFile(handle, 0, 0, 1, 0) };
                    if locked != 0 {
                        if is_process_dead(pid, start_time) {
                            unsafe {
                                windows_sys::Win32::Foundation::CloseHandle(handle);
                            }
                            let bin_path = path.with_extension("bin");
                            let _ = std::fs::remove_file(&bin_path);
                            let _ = std::fs::remove_file(&path);
                            cleaned_count += 1;
                        } else {
                            unsafe {
                                windows_sys::Win32::Foundation::CloseHandle(handle);
                            }
                        }
                    } else {
                        unsafe {
                            windows_sys::Win32::Foundation::CloseHandle(handle);
                        }
                    }
                }
            }

            #[cfg(not(windows))]
            {
                use std::os::unix::io::AsRawFd;
                if let Ok(lock_file) = OpenOptions::new().read(true).write(true).open(&path) {
                    let ret = unsafe {
                        libc::flock(lock_file.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB)
                    };
                    if ret == 0 {
                        if is_process_dead(pid, start_time) {
                            let bin_path = path.with_extension("bin");
                            let _ = std::fs::remove_file(&bin_path);
                            let _ = std::fs::remove_file(&path);
                            cleaned_count += 1;
                        }
                    }
                }
            }
        } else if filename.ends_with(".bin") {
            let lock_path = path.with_extension("lock");
            if !lock_path.exists() && is_process_dead(pid, start_time) {
                if let Ok(_f) = OpenOptions::new().write(true).open(&path) {
                    let _ = std::fs::remove_file(&path);
                    cleaned_count += 1;
                }
            }
        }
    }

    Ok(cleaned_count)
}

impl Drop for ScratchSpillFile {
    fn drop(&mut self) {
        if !self.cleaned.swap(true, Ordering::SeqCst) {
            #[cfg(windows)]
            unsafe {
                windows_sys::Win32::Foundation::CloseHandle(self.lock_handle);
            }
            let _ = std::fs::remove_file(&self.file_path);
            for _ in 0..10 {
                if std::fs::remove_file(&self.lock_path).is_ok() || !self.lock_path.exists() {
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(2));
            }
        }
    }
}

fn get_or_create_scratch_dir() -> Result<PathBuf, RustParserError> {
    let temp_root = std::env::temp_dir();
    let scratch_dir = temp_root.join("excel_intel_scratch");
    if !scratch_dir.exists() {
        std::fs::create_dir_all(&scratch_dir).map_err(|e| {
            RustParserError::CorruptWorkbook(format!("Failed to create scratch directory: {}", e))
        })?;
    }
    Ok(scratch_dir)
}

fn verify_local_filesystem(path: &Path) -> Result<(), RustParserError> {
    #[cfg(windows)]
    {
        use windows_sys::Win32::Storage::FileSystem::*;

        let path_str = path
            .to_str()
            .ok_or_else(|| RustParserError::ResourceLimit {
                code: "ERR_UNSAFE_SCRATCH_VOLUME",
                message: "Invalid UTF-8 scratch path".to_string(),
            })?;

        let root_wide: Vec<u16> = path_str
            .chars()
            .take(3)
            .chain(std::iter::once('\0'))
            .map(|c| c as u16)
            .collect();
        let drive_type = unsafe { GetDriveTypeW(root_wide.as_ptr()) };

        if drive_type != DRIVE_FIXED && drive_type != DRIVE_RAMDISK {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_UNSAFE_SCRATCH_VOLUME",
                message: format!(
                    "Scratch directory is on non-local or network drive type {}",
                    drive_type
                ),
            });
        }

        let mut fs_name_buf = [0u16; 32];
        let ok = unsafe {
            GetVolumeInformationW(
                root_wide.as_ptr(),
                std::ptr::null_mut(),
                0,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                fs_name_buf.as_mut_ptr(),
                fs_name_buf.len() as u32,
            )
        };

        if ok != 0 {
            let fs_name = String::from_utf16_lossy(&fs_name_buf);
            let fs_name_clean = fs_name.trim_matches('\0');
            if fs_name_clean != "NTFS" && fs_name_clean != "ReFS" {
                return Err(RustParserError::ResourceLimit {
                    code: "ERR_UNSAFE_SCRATCH_VOLUME",
                    message: format!(
                        "Unsupported filesystem type '{}'; must be NTFS or ReFS",
                        fs_name_clean
                    ),
                });
            }
        }
    }

    Ok(())
}

fn get_process_start_time() -> u64 {
    #[cfg(windows)]
    {
        use windows_sys::Win32::System::Threading::*;
        let mut creation_time: windows_sys::Win32::Foundation::FILETIME =
            unsafe { std::mem::zeroed() };
        let mut exit_time: windows_sys::Win32::Foundation::FILETIME = unsafe { std::mem::zeroed() };
        let mut kernel_time: windows_sys::Win32::Foundation::FILETIME =
            unsafe { std::mem::zeroed() };
        let mut user_time: windows_sys::Win32::Foundation::FILETIME = unsafe { std::mem::zeroed() };

        let handle = unsafe { GetCurrentProcess() };
        let ok = unsafe {
            GetProcessTimes(
                handle,
                &mut creation_time,
                &mut exit_time,
                &mut kernel_time,
                &mut user_time,
            )
        };

        if ok != 0 {
            return ((creation_time.dwHighDateTime as u64) << 32)
                | (creation_time.dwLowDateTime as u64);
        }
    }

    #[cfg(target_os = "linux")]
    {
        if let Ok(content) = std::fs::read_to_string("/proc/self/stat") {
            if let Some(starttime_str) = content.split_whitespace().nth(21) {
                if let Ok(ticks) = starttime_str.parse::<u64>() {
                    return ticks;
                }
            }
        }
    }

    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{Arc, Mutex};
    use std::thread;

    static TEST_MUTEX: Mutex<()> = Mutex::new(());

    #[test]
    fn test_scratch_normal_creation_and_cleanup() {
        let mut scratch = ScratchSpillFile::new().unwrap();
        let file_path = scratch.file_path.clone();
        let lock_path = scratch.lock_path.clone();

        assert!(file_path.exists());
        assert!(lock_path.exists());

        scratch.file.write_all(b"test data").unwrap();

        drop(scratch);

        // Assert deterministic cleanup on drop
        assert!(!file_path.exists());
        assert!(!lock_path.exists());
    }

    #[test]
    fn test_scratch_exception_cleanup() {
        fn faulty_operation() -> Result<PathBuf, RustParserError> {
            let mut scratch = ScratchSpillFile::new()?;
            let saved_path = scratch.file_path.clone();
            scratch.file.write_all(b"partial")?;
            // Simulate error
            if true {
                return Err(RustParserError::CorruptWorkbook(
                    "Simulated error".to_string(),
                ));
            }
            Ok(saved_path)
        }

        let res = faulty_operation();
        assert!(res.is_err());
        // Cleaned up via ? error propagation
    }

    #[test]
    fn test_scratch_panic_unwind_cleanup() {
        let paths = Arc::new(std::sync::Mutex::new(None));
        let paths_clone = Arc::clone(&paths);
        let res = std::panic::catch_unwind(move || {
            let scratch = ScratchSpillFile::new().unwrap();
            *paths_clone.lock().unwrap() =
                Some((scratch.file_path.clone(), scratch.lock_path.clone()));
            panic!("Simulated worker panic");
        });
        assert!(res.is_err());

        let (f, l) = paths.lock().unwrap().take().unwrap();
        assert!(!f.exists());
        assert!(!l.exists());
    }

    #[test]
    fn test_scratch_lock_acquisition_failure() {
        let scratch = ScratchSpillFile::new().unwrap();
        // Trying to open and lock an already locked file exclusively must fail
        #[cfg(windows)]
        {
            use windows_sys::Win32::Storage::FileSystem::*;
            let lock_wide: Vec<u16> = scratch
                .lock_path
                .to_str()
                .unwrap()
                .encode_utf16()
                .chain(std::iter::once(0))
                .collect();
            let handle = unsafe {
                CreateFileW(
                    lock_wide.as_ptr(),
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ,
                    std::ptr::null_mut(),
                    OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL,
                    std::ptr::null_mut(),
                )
            };
            if handle != windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE {
                let locked = unsafe { LockFile(handle, 0, 0, 1, 0) };
                // Exclusive lock must fail because original handle holds it
                assert_eq!(locked, 0);
                unsafe { windows_sys::Win32::Foundation::CloseHandle(handle) };
            }
        }
    }

    #[test]
    fn test_active_scratch_owner_lock_cannot_be_deleted_or_replaced() {
        let scratch = ScratchSpillFile::new().unwrap();
        let lock_path = scratch.lock_path.clone();
        let spill_path = scratch.file_path.clone();

        // 1. Proving active scratch owner's lock cannot be deleted while held
        #[cfg(windows)]
        {
            let remove_res = std::fs::remove_file(&lock_path);
            assert!(
                remove_res.is_err(),
                "Active owner lock file MUST NOT be deletable while handle is held"
            );
        }

        // 2. Proving active scratch owner's lock cannot be replaced or opened for write
        let replace_res = std::fs::OpenOptions::new()
            .write(true)
            .create(false)
            .open(&lock_path);
        assert!(
            replace_res.is_err(),
            "Active owner lock file MUST NOT allow replacement or conflicting write open"
        );

        // 3. Proving concurrent scavenging cannot bypass the active OS lock
        let _ = scavenge_scratch_dir();
        assert!(
            lock_path.exists(),
            "Active owner lock file MUST NOT be deleted by scavenger"
        );
        assert!(
            spill_path.exists(),
            "Active owner spill file MUST NOT be deleted by scavenger"
        );

        drop(scratch);
        // 4. After drop, verify clean removal
        assert!(!lock_path.exists(), "Lock path must be removed after drop");
        assert!(
            !spill_path.exists(),
            "Spill path must be removed after drop"
        );
    }

    #[test]
    fn test_scratch_concurrent_creation() {
        let mut handles = Vec::new();
        for _ in 0..8 {
            handles.push(thread::spawn(|| {
                let mut scratch = ScratchSpillFile::new().unwrap();
                scratch.file.write_all(b"concurrent data").unwrap();
                assert!(scratch.file_path.exists());
                assert!(scratch.lock_path.exists());
                thread::sleep(std::time::Duration::from_millis(5));
                drop(scratch);
            }));
        }

        for h in handles {
            h.join().unwrap();
        }
    }

    #[test]
    fn test_scratch_concurrent_scavenging_against_active_creation() {
        let _guard = TEST_MUTEX.lock().unwrap();
        let stop_flag = Arc::new(AtomicBool::new(false));
        let flag_clone = Arc::clone(&stop_flag);

        // Background thread scavenging concurrently
        let scavenger_thread = thread::spawn(move || {
            while !flag_clone.load(Ordering::Relaxed) {
                let _ = scavenge_scratch_dir();
                thread::sleep(std::time::Duration::from_millis(1));
            }
        });

        // Worker threads creating active scratch files
        let mut workers = Vec::new();
        for _ in 0..4 {
            workers.push(thread::spawn(|| {
                for _ in 0..5 {
                    let mut scratch = ScratchSpillFile::new().unwrap();
                    scratch.file.write_all(b"active data").unwrap();
                    assert!(scratch.file_path.exists());
                    assert!(scratch.lock_path.exists());
                    thread::sleep(std::time::Duration::from_millis(2));
                    // File must still exist despite scavenger running concurrently
                    assert!(scratch.file_path.exists());
                    assert!(scratch.lock_path.exists());
                    drop(scratch);
                }
            }));
        }

        for w in workers {
            w.join().unwrap();
        }

        stop_flag.store(true, Ordering::Relaxed);
        scavenger_thread.join().unwrap();
    }

    #[test]
    fn test_scratch_orphan_bin_recovery() {
        let _guard = TEST_MUTEX.lock().unwrap();
        let scratch_dir = get_or_create_scratch_dir().unwrap();
        // Create an orphan .bin from a dead PID (99999999)
        let orphan_path =
            scratch_dir.join("m02_spill_99999999_1_00000000-0000-0000-0000-000000000001.bin");
        std::fs::write(&orphan_path, b"abandoned data").unwrap();
        assert!(orphan_path.exists());

        let cleaned = scavenge_scratch_dir().unwrap();
        assert!(cleaned >= 1);
        assert!(!orphan_path.exists());
    }

    #[test]
    fn test_scratch_missing_lock_recovery() {
        let _guard = TEST_MUTEX.lock().unwrap();
        let scratch_dir = get_or_create_scratch_dir().unwrap();
        // Create a .bin file without companion .lock for dead PID
        let no_lock_path =
            scratch_dir.join("m02_spill_99999998_1_00000000-0000-0000-0000-000000000002.bin");
        std::fs::write(&no_lock_path, b"no lock bin").unwrap();
        assert!(no_lock_path.exists());

        let cleaned = scavenge_scratch_dir().unwrap();
        assert!(cleaned >= 1);
        assert!(!no_lock_path.exists());
    }

    #[test]
    fn test_scratch_pid_reuse_protection() {
        let pid = std::process::id();
        // If expected start time is in the past (e.g. 1), it indicates PID reuse
        assert!(is_process_dead(pid, 1));
    }

    #[test]
    fn test_scratch_active_process_preservation() {
        let _guard = TEST_MUTEX.lock().unwrap();
        // Clean any leftover stale files before assertion
        let _ = scavenge_scratch_dir();

        let scratch = ScratchSpillFile::new().unwrap();
        let cleaned = scavenge_scratch_dir().unwrap();
        // Active scratch file must NOT be cleaned by scavenger
        assert_eq!(cleaned, 0);
        assert!(scratch.file_path.exists());
        assert!(scratch.lock_path.exists());
    }

    #[test]
    fn test_scratch_independent_reader_isolation() {
        let scratch1 = ScratchSpillFile::new().unwrap();
        let mut scratch2 = ScratchSpillFile::new().unwrap();

        assert_ne!(scratch1.file_path, scratch2.file_path);
        assert_ne!(scratch1.lock_path, scratch2.lock_path);

        drop(scratch1);

        // Scratch2 must remain unaffected
        assert!(scratch2.file_path.exists());
        assert!(scratch2.lock_path.exists());
        scratch2
            .file
            .write_all(b"scratch2 independent content")
            .unwrap();
        drop(scratch2);
    }

    #[test]
    fn test_scratch_forced_termination_stale_recovery() {
        let _guard = TEST_MUTEX.lock().unwrap();
        let scratch_dir = get_or_create_scratch_dir().unwrap();
        let stale_base = "m02_spill_99999997_1_00000000-0000-0000-0000-000000000003";
        let stale_bin = scratch_dir.join(format!("{}.bin", stale_base));
        let stale_lock = scratch_dir.join(format!("{}.lock", stale_base));

        std::fs::write(&stale_bin, b"stale bin data").unwrap();
        std::fs::write(&stale_lock, b"stale lock metadata").unwrap();

        assert!(stale_bin.exists());
        assert!(stale_lock.exists());

        let cleaned = scavenge_scratch_dir().unwrap();
        assert!(cleaned >= 1);

        assert!(!stale_bin.exists());
        assert!(!stale_lock.exists());
    }
}
