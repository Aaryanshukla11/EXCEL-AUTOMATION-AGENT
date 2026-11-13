use crate::error::RustParserError;

pub const MAX_EXCEL_UTF16_UNITS: usize = 32_767;
pub const MAX_CELL_STRING_BYTES: usize = 131_072; // 128 KB

/// Validates decoded UTF-8 string against both Excel's 32,767 UTF-16 code-unit limit
/// and the 131,072-byte streaming ingestion buffer safety limit.
pub fn validate_cell_string(decoded_utf8: &str) -> Result<(), RustParserError> {
    // 1. Enforceable byte safety bound
    if decoded_utf8.len() > MAX_CELL_STRING_BYTES {
        return Err(RustParserError::CellTextLengthExceeded {
            reason: "Decoded UTF-8 byte length exceeds 131,072-byte safety limit",
            actual_bytes: decoded_utf8.len(),
            limit_bytes: MAX_CELL_STRING_BYTES,
        });
    }

    // 2. Excel UTF-16 code unit specification ceiling
    let mut utf16_units: usize = 0;
    for c in decoded_utf8.chars() {
        // Code points > 0xFFFF require 2 UTF-16 code units (surrogate pair)
        utf16_units += if (c as u32) > 0xFFFF { 2 } else { 1 };
        if utf16_units > MAX_EXCEL_UTF16_UNITS {
            return Err(RustParserError::CellTextLengthExceeded {
                reason: "Excel UTF-16 code-unit limit exceeded (>32,767)",
                actual_bytes: utf16_units,
                limit_bytes: MAX_EXCEL_UTF16_UNITS,
            });
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_boundary_ascii_pass() {
        let s = "a".repeat(32_767);
        // 32,767 bytes, 32,767 UTF-16 code units -> PASS
        assert!(validate_cell_string(&s).is_ok());
    }

    #[test]
    fn test_boundary_ascii_fail_utf16() {
        let s = "a".repeat(32_768);
        // 32,768 bytes (<= 131,072), but 32,768 UTF-16 units (> 32,767) -> FAILS on UTF-16 limit
        let err = validate_cell_string(&s).unwrap_err();
        assert!(matches!(
            err,
            RustParserError::CellTextLengthExceeded {
                limit_bytes: 32_767,
                ..
            }
        ));
    }

    #[test]
    fn test_boundary_cjk_bmp_max_bytes_pass() {
        // '\u{4E16}' is 3 bytes in UTF-8, 1 UTF-16 code unit
        let s = "\u{4E16}".repeat(32_767);
        // 98,301 bytes (<= 131,072), 32,767 UTF-16 code units (<= 32,767) -> PASS (Theoretical maximum valid byte length)
        assert_eq!(s.len(), 98_301);
        assert!(validate_cell_string(&s).is_ok());
    }

    #[test]
    fn test_boundary_supplementary_emoji_fail_utf16() {
        // '😀' is 4 bytes in UTF-8, 2 UTF-16 code units (surrogate pair)
        let s = "\u{1F600}".repeat(16_384);
        // 65,536 bytes (<= 131,072), but 32,768 UTF-16 units (> 32,767) -> FAILS on UTF-16 limit
        let err = validate_cell_string(&s).unwrap_err();
        assert!(matches!(
            err,
            RustParserError::CellTextLengthExceeded {
                limit_bytes: 32_767,
                ..
            }
        ));
    }

    #[test]
    fn test_boundary_buffer_overflow_fail_bytes() {
        // Raw byte payload exceeding 131,072 bytes
        let s = "a".repeat(131_073);
        // 131,073 bytes (> 131,072) -> FAILS on byte limit immediately
        let err = validate_cell_string(&s).unwrap_err();
        assert!(matches!(
            err,
            RustParserError::CellTextLengthExceeded {
                limit_bytes: 131_072,
                ..
            }
        ));
    }
}
