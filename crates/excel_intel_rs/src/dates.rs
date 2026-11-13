use crate::error::RustParserError;
use chrono::{Datelike, Timelike};
use pyo3::prelude::*;

#[derive(Debug, Clone, PartialEq)]
pub enum ExcelDateTime {
    /// Valid Gregorian date-time supported by ISO-8601 / RFC-3339
    Standard(chrono::NaiveDateTime),
    /// Valid Gregorian date-only (exact integer serial with no time component)
    StandardDate(chrono::NaiveDate),
    /// Time-only value derived from fractional serials < 1.0 in the 1900 system
    TimeOnly(chrono::NaiveTime),
    /// Excel 1900-system unanchored serial zero (0.0)
    SerialZero,
    /// Excel 1900-system fictitious leap day (Serial 60.0 to 60.99999999)
    Fictitious1900Feb29 { time: Option<chrono::NaiveTime> },
}

impl IntoPy<PyObject> for ExcelDateTime {
    fn into_py(self, py: Python<'_>) -> PyObject {
        let dt_mod = match py.import_bound("datetime") {
            Ok(m) => m,
            Err(_) => return py.None(),
        };

        match self {
            Self::Standard(dt) => {
                let py_dt = dt_mod.getattr("datetime").and_then(|cls| {
                    cls.call1((
                        dt.year(),
                        dt.month(),
                        dt.day(),
                        dt.hour(),
                        dt.minute(),
                        dt.second(),
                        dt.nanosecond() / 1_000,
                    ))
                });
                match py_dt {
                    Ok(v) => v.into_py(py),
                    Err(_) => dt.to_string().into_py(py),
                }
            }
            Self::StandardDate(d) => {
                let py_d = dt_mod
                    .getattr("date")
                    .and_then(|cls| cls.call1((d.year(), d.month(), d.day())));
                match py_d {
                    Ok(v) => v.into_py(py),
                    Err(_) => d.to_string().into_py(py),
                }
            }
            Self::TimeOnly(t) => {
                let py_t = dt_mod.getattr("time").and_then(|cls| {
                    cls.call1((t.hour(), t.minute(), t.second(), t.nanosecond() / 1_000))
                });
                match py_t {
                    Ok(v) => v.into_py(py),
                    Err(_) => t.to_string().into_py(py),
                }
            }
            Self::SerialZero => "EXCEL_SERIAL_ZERO".into_py(py),
            Self::Fictitious1900Feb29 { time } => {
                let dict = pyo3::types::PyDict::new_bound(py);
                dict.set_item("__excel_special_date__", "1900-02-29")
                    .unwrap();
                if let Some(t) = time {
                    dict.set_item("time", t.to_string()).unwrap();
                }
                dict.into_py(py)
            }
        }
    }
}

pub const MS_PER_DAY: f64 = 86_400_000.0;
pub const HALF_MS_DAY_FRAC: f64 = 0.5 / MS_PER_DAY; // ~5.787037e-9 days

// Upper floating-point limits: serials >= these bounds round into year 10000
pub const UPPER_BOUND_1900_EXCLUSIVE: f64 = 2_958_466.0 - HALF_MS_DAY_FRAC;
pub const UPPER_BOUND_1904_EXCLUSIVE: f64 = 2_957_004.0 - HALF_MS_DAY_FRAC;

pub fn parse_excel_serial(serial: f64, is_1904: bool) -> Result<ExcelDateTime, RustParserError> {
    // 1. Safe floating-point pre-validation (Prevents float saturation & NaN/Inf issues)
    if serial.is_nan() || serial.is_infinite() {
        return Err(RustParserError::InvalidNumericSerial(
            "Serial must be finite",
        ));
    }
    if serial < 0.0 {
        return Err(RustParserError::DateOutOfRange(serial));
    }

    let upper_bound = if is_1904 {
        UPPER_BOUND_1904_EXCLUSIVE
    } else {
        UPPER_BOUND_1900_EXCLUSIVE
    };

    if serial >= upper_bound {
        return Err(RustParserError::DateOutOfRange(serial));
    }

    // At this point, serial is strictly in [0.0, 2_958_465.9999999942)
    // Conversion to i64 is provably safe: whole_days is at most 2_958_465
    let mut whole_days = serial.floor() as i64;
    let frac = serial - (whole_days as f64);

    // 2. Millisecond rounding and day-carry calculation
    let mut time_opt: Option<chrono::NaiveTime> = None;
    if frac >= HALF_MS_DAY_FRAC {
        let rounded_ms = (frac * MS_PER_DAY).round() as u64;
        if rounded_ms >= 86_400_000 {
            // Day carry rollover (e.g. 23:59:59.9995 -> carries to next day 00:00:00.000)
            whole_days += 1;
            time_opt = Some(chrono::NaiveTime::from_hms_milli_opt(0, 0, 0, 0).unwrap());
        } else {
            let secs = (rounded_ms / 1000) as u32;
            let ms = (rounded_ms % 1000) as u32;
            time_opt = Some(
                chrono::NaiveTime::from_num_seconds_from_midnight_opt(secs, ms * 1_000_000)
                    .unwrap(),
            );
        }
    }

    // 3. Evaluate 1904 Date System (Completely independent pipeline)
    if is_1904 {
        let base_date = chrono::NaiveDate::from_ymd_opt(1904, 1, 1).unwrap();
        let date = base_date + chrono::Duration::days(whole_days);
        return Ok(match time_opt {
            Some(t) => ExcelDateTime::Standard(date.and_time(t)),
            None => ExcelDateTime::StandardDate(date),
        });
    }

    // 4. Evaluate 1900 Date System
    if whole_days == 0 {
        return match time_opt {
            Some(t) => Ok(ExcelDateTime::TimeOnly(t)),
            None => Ok(ExcelDateTime::SerialZero),
        };
    }

    if whole_days < 60 {
        // Serial 1 = 1900-01-01
        let base_date = chrono::NaiveDate::from_ymd_opt(1899, 12, 31).unwrap();
        let date = base_date + chrono::Duration::days(whole_days);
        Ok(match time_opt {
            Some(t) => ExcelDateTime::Standard(date.and_time(t)),
            None => ExcelDateTime::StandardDate(date),
        })
    } else if whole_days == 60 {
        // Fictitious 1900-02-29 defect
        Ok(ExcelDateTime::Fictitious1900Feb29 { time: time_opt })
    } else {
        // Serial 61 = 1900-03-01 (offset by 1 day)
        let base_date = chrono::NaiveDate::from_ymd_opt(1899, 12, 30).unwrap();
        let date = base_date + chrono::Duration::days(whole_days);
        Ok(match time_opt {
            Some(t) => ExcelDateTime::Standard(date.and_time(t)),
            None => ExcelDateTime::StandardDate(date),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{NaiveDate, NaiveTime};

    #[test]
    fn test_extreme_floats_rejected_without_overflow() {
        for is_1904 in [false, true] {
            assert!(matches!(
                parse_excel_serial(f64::MAX, is_1904),
                Err(RustParserError::DateOutOfRange(_))
            ));
            assert!(matches!(
                parse_excel_serial(1e300, is_1904),
                Err(RustParserError::DateOutOfRange(_))
            ));
            assert!(matches!(
                parse_excel_serial(i64::MAX as f64, is_1904),
                Err(RustParserError::DateOutOfRange(_))
            ));
            assert!(matches!(
                parse_excel_serial(3e6, is_1904),
                Err(RustParserError::DateOutOfRange(_))
            ));
            assert!(matches!(
                parse_excel_serial(-1.0, is_1904),
                Err(RustParserError::DateOutOfRange(_))
            ));
            assert!(matches!(
                parse_excel_serial(f64::NAN, is_1904),
                Err(RustParserError::InvalidNumericSerial(_))
            ));
        }
    }

    #[test]
    fn test_1900_ieee754_adjacent_boundary_values() {
        let upper_bound = UPPER_BOUND_1900_EXCLUSIVE;
        let upper_bits = upper_bound.to_bits();

        // 1. previous = bits - 1 -> MUST BE ACCEPTED (9999-12-31 23:59:59.999)
        let prev_serial = f64::from_bits(upper_bits - 1);
        let res_prev = parse_excel_serial(prev_serial, false).unwrap();
        assert_eq!(
            res_prev,
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(9999, 12, 31)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(23, 59, 59, 999).unwrap())
            )
        );

        // 2. upper_bound -> MUST BE REJECTED (DateOutOfRange)
        assert!(matches!(
            parse_excel_serial(upper_bound, false),
            Err(RustParserError::DateOutOfRange(_))
        ));

        // 3. next = bits + 1 -> MUST BE REJECTED (DateOutOfRange)
        let next_serial = f64::from_bits(upper_bits + 1);
        assert!(matches!(
            parse_excel_serial(next_serial, false),
            Err(RustParserError::DateOutOfRange(_))
        ));
    }

    #[test]
    fn test_1904_ieee754_adjacent_boundary_values() {
        let upper_bound = UPPER_BOUND_1904_EXCLUSIVE;
        let upper_bits = upper_bound.to_bits();

        // 1. previous = bits - 1 -> MUST BE ACCEPTED (9999-12-31 23:59:59.999)
        let prev_serial = f64::from_bits(upper_bits - 1);
        let res_prev = parse_excel_serial(prev_serial, true).unwrap();
        assert_eq!(
            res_prev,
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(9999, 12, 31)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(23, 59, 59, 999).unwrap())
            )
        );

        // 2. upper_bound -> MUST BE REJECTED (DateOutOfRange)
        assert!(matches!(
            parse_excel_serial(upper_bound, true),
            Err(RustParserError::DateOutOfRange(_))
        ));

        // 3. next = bits + 1 -> MUST BE REJECTED (DateOutOfRange)
        let next_serial = f64::from_bits(upper_bits + 1);
        assert!(matches!(
            parse_excel_serial(next_serial, true),
            Err(RustParserError::DateOutOfRange(_))
        ));
    }

    #[test]
    fn test_1904_previous_millisecond_coverage() {
        let max_day_1904 = 2_957_003.0; // 9999-12-31 in 1904 system

        // Previous millisecond (23:59:59.998)
        let s_prev_ms = max_day_1904 + (86_399_998.0 / 86_400_000.0);
        let res = parse_excel_serial(s_prev_ms, true).unwrap();
        assert_eq!(
            res,
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(9999, 12, 31)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(23, 59, 59, 998).unwrap())
            )
        );

        // Exact millisecond (23:59:59.999)
        let s_exact_ms = max_day_1904 + (86_399_999.0 / 86_400_000.0);
        let res_exact = parse_excel_serial(s_exact_ms, true).unwrap();
        assert_eq!(
            res_exact,
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(9999, 12, 31)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(23, 59, 59, 999).unwrap())
            )
        );
    }

    #[test]
    fn test_regression_serials_0_to_1_5() {
        // 1900 System
        assert_eq!(
            parse_excel_serial(0.0, false).unwrap(),
            ExcelDateTime::SerialZero
        );
        assert_eq!(
            parse_excel_serial(0.5, false).unwrap(),
            ExcelDateTime::TimeOnly(NaiveTime::from_hms_milli_opt(12, 0, 0, 0).unwrap())
        );
        assert_eq!(
            parse_excel_serial(1.0, false).unwrap(),
            ExcelDateTime::StandardDate(NaiveDate::from_ymd_opt(1900, 1, 1).unwrap())
        );
        assert_eq!(
            parse_excel_serial(1.5, false).unwrap(),
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(1900, 1, 1)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(12, 0, 0, 0).unwrap())
            )
        );

        // 1904 System
        assert_eq!(
            parse_excel_serial(0.0, true).unwrap(),
            ExcelDateTime::StandardDate(NaiveDate::from_ymd_opt(1904, 1, 1).unwrap())
        );
        assert_eq!(
            parse_excel_serial(0.5, true).unwrap(),
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(1904, 1, 1)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(12, 0, 0, 0).unwrap())
            )
        );
        assert_eq!(
            parse_excel_serial(1.0, true).unwrap(),
            ExcelDateTime::StandardDate(NaiveDate::from_ymd_opt(1904, 1, 2).unwrap())
        );
        assert_eq!(
            parse_excel_serial(1.5, true).unwrap(),
            ExcelDateTime::Standard(
                NaiveDate::from_ymd_opt(1904, 1, 2)
                    .unwrap()
                    .and_time(NaiveTime::from_hms_milli_opt(12, 0, 0, 0).unwrap())
            )
        );
    }

    #[test]
    fn test_serial_60_fictitious_leap_day() {
        let res60 = parse_excel_serial(60.0, false).unwrap();
        assert_eq!(res60, ExcelDateTime::Fictitious1900Feb29 { time: None });

        let res60_noon = parse_excel_serial(60.5, false).unwrap();
        assert_eq!(
            res60_noon,
            ExcelDateTime::Fictitious1900Feb29 {
                time: Some(NaiveTime::from_hms_milli_opt(12, 0, 0, 0).unwrap())
            }
        );
    }
}
