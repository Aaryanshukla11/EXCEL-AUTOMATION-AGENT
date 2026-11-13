use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;

// Python exception hierarchy
create_exception!(excel_intel._rs, ParserError, PyException);
create_exception!(excel_intel._rs, PlatformResourceLimitError, ParserError);
create_exception!(excel_intel._rs, DateOutOfRangeError, ParserError);
create_exception!(excel_intel._rs, CorruptWorkbookError, ParserError);
create_exception!(excel_intel._rs, UnsupportedFormatError, ParserError);

#[derive(Debug)]
pub enum RustParserError {
    ResourceLimit {
        code: &'static str,
        message: String,
    },
    DateOutOfRange(f64),
    InvalidNumericSerial(&'static str),
    InvalidTimeFraction(f64),
    CellTextLengthExceeded {
        reason: &'static str,
        actual_bytes: usize,
        limit_bytes: usize,
    },
    CorruptWorkbook(String),
    UnsupportedFormat(String),
    Io(std::io::Error),
    Xml(quick_xml::Error),
    Zip(zip::result::ZipError),
}

impl std::fmt::Display for RustParserError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ResourceLimit { code, message } => {
                write!(f, "PlatformResourceLimitError [{}]: {}", code, message)
            }
            Self::DateOutOfRange(s) => write!(
                f,
                "DateOutOfRange: Serial {} is outside supported calendar boundaries",
                s
            ),
            Self::InvalidNumericSerial(msg) => write!(f, "InvalidNumericSerial: {}", msg),
            Self::InvalidTimeFraction(frac) => write!(f, "InvalidTimeFraction: {}", frac),
            Self::CellTextLengthExceeded {
                reason,
                actual_bytes,
                limit_bytes,
            } => {
                write!(
                    f,
                    "CellTextLengthExceeded: {} (actual={}, limit={})",
                    reason, actual_bytes, limit_bytes
                )
            }
            Self::CorruptWorkbook(msg) => write!(f, "CorruptWorkbook: {}", msg),
            Self::UnsupportedFormat(msg) => write!(f, "UnsupportedFormat: {}", msg),
            Self::Io(err) => write!(f, "IO Error: {}", err),
            Self::Xml(err) => write!(f, "XML Error: {}", err),
            Self::Zip(err) => write!(f, "ZIP Error: {}", err),
        }
    }
}

impl std::error::Error for RustParserError {}

impl From<std::io::Error> for RustParserError {
    fn from(err: std::io::Error) -> Self {
        Self::Io(err)
    }
}

impl From<quick_xml::Error> for RustParserError {
    fn from(err: quick_xml::Error) -> Self {
        Self::Xml(err)
    }
}

impl From<zip::result::ZipError> for RustParserError {
    fn from(err: zip::result::ZipError) -> Self {
        match &err {
            zip::result::ZipError::UnsupportedArchive(msg) => {
                let msg_lower = msg.to_lowercase();
                if msg_lower.contains("password") || msg_lower.contains("encrypted") {
                    Self::UnsupportedFormat(format!(
                        "Encrypted workbooks are not supported: {}",
                        msg
                    ))
                } else {
                    Self::Zip(err)
                }
            }
            _ => Self::Zip(err),
        }
    }
}

impl From<RustParserError> for PyErr {
    fn from(err: RustParserError) -> PyErr {
        match err {
            RustParserError::ResourceLimit { .. }
            | RustParserError::CellTextLengthExceeded { .. } => {
                PlatformResourceLimitError::new_err(err.to_string())
            }
            RustParserError::DateOutOfRange(_) => DateOutOfRangeError::new_err(err.to_string()),
            RustParserError::CorruptWorkbook(_)
            | RustParserError::Xml(_)
            | RustParserError::Zip(_) => CorruptWorkbookError::new_err(err.to_string()),
            RustParserError::UnsupportedFormat(_) => {
                UnsupportedFormatError::new_err(err.to_string())
            }
            _ => ParserError::new_err(err.to_string()),
        }
    }
}
