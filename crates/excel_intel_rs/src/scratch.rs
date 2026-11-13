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

            let file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
                .open(&file_path)
                .map_err(|e| {
                    RustParserError::CorruptWorkbook(format!(
                        "Failed to create scratch spill file: {}",
                        e
                    ))
                })?;

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
                let _ = std::fs::remove_file(&file_path);
                return Err(RustParserError::CorruptWorkbook(
                    "Failed to acquire scratch lock handle".to_string(),
                ));
            }

            let locked = unsafe { LockFile(lock_handle, 0, 0, 1, 0) };

            if locked == 0 {
                unsafe { windows_sys::Win32::Foundation::CloseHandle(lock_handle) };
                let _ = std::fs::remove_file(&file_path);
                let _ = std::fs::remove_file(&lock_path);
                return Err(RustParserError::CorruptWorkbook(
                    "Failed to lock scratch lock file exclusively".to_string(),
                ));
            }

            (file, lock_handle)
        };

        #[cfg(not(windows))]
        let (file, lock_handle) = {
            let file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(&file_path)
                .map_err(|e| {
                    RustParserError::CorruptWorkbook(format!(
                        "Failed to create scratch file: {}",
                        e
                    ))
                })?;
            let _lock_file = OpenOptions::new()
                .read(true)
                .write(true)
                .create_new(true)
                .open(&lock_path)
                .map_err(|e| {
                    RustParserError::CorruptWorkbook(format!("Failed to create lock file: {}", e))
                })?;
            (file, ())
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

impl Drop for ScratchSpillFile {
    fn drop(&mut self) {
        if !self.cleaned.swap(true, Ordering::SeqCst) {
            #[cfg(windows)]
            unsafe {
                windows_sys::Win32::Foundation::CloseHandle(self.lock_handle);
            }
            let _ = std::fs::remove_file(&self.file_path);
            let _ = std::fs::remove_file(&self.lock_path);
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

    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
