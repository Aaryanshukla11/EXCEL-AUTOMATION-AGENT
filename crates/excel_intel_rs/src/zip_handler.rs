use crate::error::RustParserError;
use std::fs::File;
use std::io::{BufReader, Read, Seek, Write};
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use zip::ZipArchive;

pub const MAX_DECOMPRESSED_ZIP_BYTES: u64 = 1_073_741_824; // 1.0 GiB approved limit
pub const MAX_RATIO_OUTPUT_THRESHOLD: u64 = 10 * 1024 * 1024; // 10.0 MB
pub const MAX_COMPRESSION_RATIO: f64 = 10.0; // 10.0x ratio guard against zip bombs (approved frozen architecture)

const OLE_SIGNATURE: [u8; 8] = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
const ZIP_LOCAL_HEADER: [u8; 4] = [0x50, 0x4B, 0x03, 0x04];
const ZIP_SPANNED_HEADER: [u8; 4] = [0x50, 0x4B, 0x07, 0x08];
const EOCD_SIGNATURE: [u8; 4] = [0x50, 0x4B, 0x05, 0x06];
const ZIP64_EOCD_LOCATOR_SIG: [u8; 4] = [0x50, 0x4B, 0x06, 0x07];
const ZIP64_EOCD_RECORD_SIG: [u8; 4] = [0x50, 0x4B, 0x06, 0x06];

pub struct ZipPackageReader {
    archive: ZipArchive<BufReader<File>>,
    total_decompressed_bytes: AtomicU64,
    compressed_file_size: u64,
    has_macros: bool,
}

impl ZipPackageReader {
    pub fn open(path: &Path) -> Result<Self, RustParserError> {
        let mut file = File::open(path)?;
        let file_meta = file.metadata()?;
        let compressed_file_size = file_meta.len();

        let mut header = [0u8; 8];
        let bytes_read = file.read(&mut header)?;
        if bytes_read >= 8 && header == OLE_SIGNATURE {
            return Err(RustParserError::UnsupportedFormat(
                "Unsupported OLE / Compound File format".to_string(),
            ));
        }

        if bytes_read >= 4 && header[0..4] == ZIP_SPANNED_HEADER {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_UNSUPPORTED_ZIP_SPANNED",
                message: "Spanned or split ZIP archives are not supported".to_string(),
            });
        }

        if bytes_read < 4 || header[0..4] != ZIP_LOCAL_HEADER {
            return Err(RustParserError::CorruptWorkbook(
                "Invalid workbook container header".to_string(),
            ));
        }

        // Structural ZIP64 validation relative to EOCD record
        Self::check_zip64_structure(&mut file, compressed_file_size)?;

        file.seek(std::io::SeekFrom::Start(0))?;
        let reader = BufReader::with_capacity(64 * 1024, file);
        let mut archive = ZipArchive::new(reader)?;

        // Validate encryption across entries
        for i in 0..archive.len() {
            let entry = archive.by_index(i)?;
            if entry.encrypted() {
                return Err(RustParserError::UnsupportedFormat(
                    "Encrypted or password-protected workbooks are not supported".to_string(),
                ));
            }
        }

        // Validate required OpenXML package entries
        if archive.by_name("[Content_Types].xml").is_err() {
            return Err(RustParserError::CorruptWorkbook(
                "Missing required package entry: [Content_Types].xml".to_string(),
            ));
        }
        if archive.by_name("xl/workbook.xml").is_err() {
            return Err(RustParserError::CorruptWorkbook(
                "Missing required package entry: xl/workbook.xml".to_string(),
            ));
        }

        let has_macros = archive.by_name("xl/vbaProject.bin").is_ok();

        Ok(Self {
            archive,
            total_decompressed_bytes: AtomicU64::new(0),
            compressed_file_size,
            has_macros,
        })
    }

    fn check_zip64_structure(file: &mut File, file_size: u64) -> Result<(), RustParserError> {
        if file_size > 4 * 1024 * 1024 * 1024 {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_UNSUPPORTED_ZIP64",
                message: "ZIP64 archives exceeding 4 GB are not supported for Excel workbooks"
                    .to_string(),
            });
        }

        if file_size < 22 {
            return Err(RustParserError::CorruptWorkbook(
                "ZIP archive is too small".to_string(),
            ));
        }

        // Minimum EOCD is 22 bytes. Maximum comment length in ZIP is 65,535 bytes.
        // Include extra 20 bytes to encompass a potential ZIP64 locator preceding EOCD.
        let max_read = std::cmp::min(file_size, 22 + 65_535 + 20) as usize;
        let seek_pos = file_size - (max_read as u64);
        file.seek(std::io::SeekFrom::Start(seek_pos))?;
        let mut buffer = vec![0u8; max_read];
        file.read_exact(&mut buffer)?;

        // Scan backwards for the true EOCD record: PK\x05\x06
        let mut eocd_rel_offset: Option<usize> = None;
        for i in (0..=(buffer.len() - 22)).rev() {
            if buffer[i..i + 4] == EOCD_SIGNATURE {
                let comment_len = u16::from_le_bytes([buffer[i + 20], buffer[i + 21]]) as usize;
                if i + 22 + comment_len == buffer.len() {
                    eocd_rel_offset = Some(i);
                    break;
                }
            }
        }

        let eocd_offset = match eocd_rel_offset {
            Some(offset) => offset,
            None => {
                return Err(RustParserError::CorruptWorkbook(
                    "End of Central Directory record not found".to_string(),
                ));
            }
        };

        // 1. EOCD 16-bit / 32-bit overflow fields indicating ZIP64
        let disk_entries = u16::from_le_bytes([buffer[eocd_offset + 8], buffer[eocd_offset + 9]]);
        let total_entries =
            u16::from_le_bytes([buffer[eocd_offset + 10], buffer[eocd_offset + 11]]);
        let cd_size = u32::from_le_bytes([
            buffer[eocd_offset + 12],
            buffer[eocd_offset + 13],
            buffer[eocd_offset + 14],
            buffer[eocd_offset + 15],
        ]);
        let cd_offset = u32::from_le_bytes([
            buffer[eocd_offset + 16],
            buffer[eocd_offset + 17],
            buffer[eocd_offset + 18],
            buffer[eocd_offset + 19],
        ]);

        if disk_entries == 0xFFFF
            || total_entries == 0xFFFF
            || cd_size == 0xFFFFFFFF
            || cd_offset == 0xFFFFFFFF
        {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_UNSUPPORTED_ZIP64",
                message: "ZIP64 archives are not supported for Excel workbooks; container exceeds 4 GB or 65,535 entry limit".to_string(),
            });
        }

        // 2. Validate genuine ZIP64 locator immediately preceding EOCD (eocd_offset - 20)
        if eocd_offset >= 20 {
            let locator_offset = eocd_offset - 20;
            if buffer[locator_offset..locator_offset + 4] == ZIP64_EOCD_LOCATOR_SIG {
                let zip64_eocd_rel_offset = u64::from_le_bytes([
                    buffer[locator_offset + 8],
                    buffer[locator_offset + 9],
                    buffer[locator_offset + 10],
                    buffer[locator_offset + 11],
                    buffer[locator_offset + 12],
                    buffer[locator_offset + 13],
                    buffer[locator_offset + 14],
                    buffer[locator_offset + 15],
                ]);

                if zip64_eocd_rel_offset + 4 <= file_size {
                    file.seek(std::io::SeekFrom::Start(zip64_eocd_rel_offset))?;
                    let mut sig = [0u8; 4];
                    if file.read_exact(&mut sig).is_ok() && sig == ZIP64_EOCD_RECORD_SIG {
                        return Err(RustParserError::ResourceLimit {
                            code: "ERR_UNSUPPORTED_ZIP64",
                            message: "ZIP64 archives are not supported for Excel workbooks; container exceeds 4 GB or 65,535 entry limit".to_string(),
                        });
                    }
                } else {
                    return Err(RustParserError::ResourceLimit {
                        code: "ERR_UNSUPPORTED_ZIP64",
                        message: "ZIP64 archives are not supported for Excel workbooks; container exceeds 4 GB or 65,535 entry limit".to_string(),
                    });
                }
            }
        }

        Ok(())
    }

    pub fn has_macros(&self) -> bool {
        self.has_macros
    }

    pub fn file_names(&self) -> Vec<String> {
        self.archive.file_names().map(|s| s.to_string()).collect()
    }

    pub fn read_file_to_string(&mut self, name: &str) -> Result<Option<String>, RustParserError> {
        let mut zip_file = match self.archive.by_name(name) {
            Ok(f) => f,
            Err(zip::result::ZipError::FileNotFound) => return Ok(None),
            Err(e) => return Err(e.into()),
        };

        let mut output = String::with_capacity(zip_file.size() as usize);
        let mut chunk = [0u8; 8192];

        let total_bytes_ref = &self.total_decompressed_bytes;
        let compressed_size = self.compressed_file_size;

        loop {
            let n = zip_file.read(&mut chunk)?;
            if n == 0 {
                break;
            }
            Self::check_and_add_bytes(total_bytes_ref, compressed_size, n as u64)?;
            let text_chunk = std::str::from_utf8(&chunk[..n]).map_err(|e| {
                RustParserError::CorruptWorkbook(format!(
                    "Invalid UTF-8 in zip entry {}: {}",
                    name, e
                ))
            })?;
            output.push_str(text_chunk);
        }

        Ok(Some(output))
    }

    pub fn extract_file_to_scratch(
        &mut self,
        name: &str,
        dest: &mut File,
    ) -> Result<u64, RustParserError> {
        let mut zip_file = match self.archive.by_name(name) {
            Ok(f) => f,
            Err(zip::result::ZipError::FileNotFound) => {
                return Err(RustParserError::CorruptWorkbook(format!(
                    "File '{}' not found in zip",
                    name
                )))
            }
            Err(e) => return Err(e.into()),
        };

        let mut chunk = [0u8; 64 * 1024];
        let mut total_written = 0u64;

        let total_bytes_ref = &self.total_decompressed_bytes;
        let compressed_size = self.compressed_file_size;

        loop {
            let n = zip_file.read(&mut chunk)?;
            if n == 0 {
                break;
            }
            Self::check_and_add_bytes(total_bytes_ref, compressed_size, n as u64)?;
            dest.write_all(&chunk[..n])?;
            total_written += n as u64;
        }

        dest.flush()?;
        Ok(total_written)
    }

    pub fn check_and_add_bytes(
        total_bytes: &AtomicU64,
        compressed_file_size: u64,
        n: u64,
    ) -> Result<(), RustParserError> {
        let prev = total_bytes.fetch_add(n, Ordering::SeqCst);
        let current = prev + n;

        if current > MAX_DECOMPRESSED_ZIP_BYTES {
            return Err(RustParserError::ResourceLimit {
                code: "ERR_ZIP_DECOMPRESSION_BOMB",
                message: format!("Decompressed bytes ({}) exceeded 1.0 GiB ceiling", current),
            });
        }

        if current > MAX_RATIO_OUTPUT_THRESHOLD && compressed_file_size > 0 {
            let ratio = (current as f64) / (compressed_file_size as f64);
            if ratio > MAX_COMPRESSION_RATIO {
                return Err(RustParserError::ResourceLimit {
                    code: "ERR_ZIP_DECOMPRESSION_BOMB",
                    message: format!(
                        "Compression ratio ({:.2}x) exceeds maximum allowed 10.0x limit",
                        ratio
                    ),
                });
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compression_ratio_below_threshold_pass() {
        // Output > 10 MB, ratio < 10.0:1 -> MUST PASS
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 15_000_000; // 15.0 MB (ratio = 7.5x < 10.0x)
        assert!(
            ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok()
        );
    }

    #[test]
    fn test_compression_ratio_at_threshold_pass() {
        // Output > 10 MB, ratio == exact 10.0:1 -> MUST PASS (at-threshold behavior is accepted)
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 20_000_000; // 20.0 MB (ratio = 10.0x == 10.0x)
        assert!(
            ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok()
        );
    }

    #[test]
    fn test_compression_ratio_above_threshold_fail() {
        // Output > 10 MB, ratio > 10.0:1 -> MUST FAIL
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 20_000_001; // 20.0 MB + 1 byte (ratio = 10.0000005x > 10.0x)
        let err = ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed)
            .unwrap_err();
        match err {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_ZIP_DECOMPRESSION_BOMB");
                assert!(message.contains("10.0x limit"));
            }
            _ => panic!("Expected ResourceLimit error"),
        }
    }

    #[test]
    fn test_compression_ratio_high_ratio_before_10mb_pass() {
        // Output <= 10 MB, high ratio (90x) -> MUST NOT prematurely trip
        let total = AtomicU64::new(0);
        let compressed_size = 100_000; // 100 KB
        let decompressed = 9_000_000; // 9.0 MB (ratio = 90.0x > 10.0x, but output <= 10 MB threshold)
        assert!(
            ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok()
        );
    }

    #[test]
    fn test_compression_ratio_cumulative_1gib_quota_independent_fail() {
        // Low ratio (e.g. 5x), but cumulative output > 1.0 GiB -> MUST FAIL on independent 1.0 GiB ceiling
        let total = AtomicU64::new(0);
        let compressed_size = 250_000_000; // 250 MB
        let decompressed = 1_073_741_825; // 1 GiB + 1 byte (ratio ~4.3x < 10.0x)
        let err = ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed)
            .unwrap_err();
        match err {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_ZIP_DECOMPRESSION_BOMB");
                assert!(message.contains("1.0 GiB ceiling"));
            }
            _ => panic!("Expected ResourceLimit error"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compression_ratio_below_threshold_pass() {
        // Output > 10 MB, ratio < 10.0:1 -> MUST PASS
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 15_000_000; // 15.0 MB (ratio = 7.5x < 10.0x)
        assert!(ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok());
    }

    #[test]
    fn test_compression_ratio_at_threshold_pass() {
        // Output > 10 MB, ratio == exact 10.0:1 -> MUST PASS (at-threshold behavior is accepted)
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 20_000_000; // 20.0 MB (ratio = 10.0x == 10.0x)
        assert!(ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok());
    }

    #[test]
    fn test_compression_ratio_above_threshold_fail() {
        // Output > 10 MB, ratio > 10.0:1 -> MUST FAIL
        let total = AtomicU64::new(0);
        let compressed_size = 2_000_000; // 2.0 MB
        let decompressed = 20_000_001; // 20.0 MB + 1 byte (ratio = 10.0000005x > 10.0x)
        let err = ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).unwrap_err();
        match err {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_ZIP_DECOMPRESSION_BOMB");
                assert!(message.contains("10.0x limit"));
            }
            _ => panic!("Expected ResourceLimit error"),
        }
    }

    #[test]
    fn test_compression_ratio_high_ratio_before_10mb_pass() {
        // Output <= 10 MB, high ratio (90x) -> MUST NOT prematurely trip
        let total = AtomicU64::new(0);
        let compressed_size = 100_000; // 100 KB
        let decompressed = 9_000_000; // 9.0 MB (ratio = 90.0x > 10.0x, but output <= 10 MB threshold)
        assert!(ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).is_ok());
    }

    #[test]
    fn test_compression_ratio_cumulative_1gib_quota_independent_fail() {
        // Low ratio (e.g. 5x), but cumulative output > 1.0 GiB -> MUST FAIL on independent 1.0 GiB ceiling
        let total = AtomicU64::new(0);
        let compressed_size = 250_000_000; // 250 MB
        let decompressed = 1_073_741_825; // 1 GiB + 1 byte (ratio ~4.3x < 10.0x)
        let err = ZipPackageReader::check_and_add_bytes(&total, compressed_size, decompressed).unwrap_err();
        match err {
            RustParserError::ResourceLimit { code, message } => {
                assert_eq!(code, "ERR_ZIP_DECOMPRESSION_BOMB");
                assert!(message.contains("1.0 GiB ceiling"));
            }
            _ => panic!("Expected ResourceLimit error"),
        }
    }
}
