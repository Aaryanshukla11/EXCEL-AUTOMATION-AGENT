use crate::cell_validator::validate_cell_string;
use crate::dates::{parse_excel_serial, ExcelDateTime};
use crate::error::RustParserError;
use crate::memory_guard::check_memory_guard;
use crate::shared_strings::SharedStringsTable;
use crate::styles::StylesTable;
use quick_xml::events::Event;
use quick_xml::Reader;
use std::io::BufRead;

#[derive(Debug, Clone, PartialEq)]
pub enum CellValue {
    Empty,
    Text(String),
    Int(i64),
    Float(f64),
    Bool(bool),
    DateTime(ExcelDateTime),
    Error(String),
}

#[derive(Debug, Clone)]
pub struct CellRecord {
    pub col: u32, // 1-indexed column
    pub coordinate: String,
    pub cell_type: Option<String>,
    pub value: CellValue,
    pub formula: Option<String>,
    pub formula_type: Option<String>,
    pub formula_ref: Option<String>,
    pub formula_si: Option<u32>,
}

#[derive(Debug, Clone)]
pub struct RowRecord {
    pub row: u32, // 1-indexed row number
    pub cells: Vec<CellRecord>,
}

pub struct StreamingWorksheetParser<R: BufRead> {
    reader: Reader<R>,
    shared_strings: std::sync::Arc<SharedStringsTable>,
    styles: std::sync::Arc<StylesTable>,
    is_1904: bool,
    processed_rows: usize,
    seen_worksheet_end: bool,
}

impl<R: BufRead> StreamingWorksheetParser<R> {
    pub fn new(
        buf_reader: R,
        shared_strings: std::sync::Arc<SharedStringsTable>,
        styles: std::sync::Arc<StylesTable>,
        is_1904: bool,
    ) -> Self {
        let mut reader = Reader::from_reader(buf_reader);
        reader.config_mut().trim_text(false);
        Self {
            reader,
            shared_strings,
            styles,
            is_1904,
            processed_rows: 0,
            seen_worksheet_end: false,
        }
    }

    pub fn next_row_chunk(
        &mut self,
        chunk_size: usize,
    ) -> Result<Option<Vec<RowRecord>>, RustParserError> {
        let mut chunk = Vec::with_capacity(chunk_size);
        let mut buf = Vec::with_capacity(512);

        let mut current_row: Option<RowRecord> = None;
        let mut current_row_num: u32 = 0;
        let mut current_cell_col: u32 = 0;
        let mut current_cell_coord = String::new();
        let mut current_cell_type: Option<String> = None;
        let mut current_cell_style: Option<usize> = None;

        let mut in_v = false;
        let mut in_f = false;
        let mut in_is = false;
        let mut in_t = false;

        let mut f_type: Option<String> = None;
        let mut f_ref: Option<String> = None;
        let mut f_si: Option<u32> = None;

        let mut v_content = String::new();
        let mut f_content = String::new();
        let mut is_content = String::new();
        let mut last_row_cells = 32;

        loop {
            match self.reader.read_event_into(&mut buf) {
                Ok(ref event @ (Event::Start(ref e) | Event::Empty(ref e))) => {
                    let is_start = matches!(event, Event::Start(_));
                    let name = e.name();
                    if name.as_ref() == b"row" {
                        let mut row_num: u32 = (self.processed_rows + chunk.len() + 1) as u32;
                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"r" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    row_num = s.parse().unwrap_or(row_num);
                                }
                            }
                        }
                        current_row_num = row_num;
                        current_cell_col = 0;
                        current_row = Some(RowRecord {
                            row: row_num,
                            cells: Vec::with_capacity(last_row_cells),
                        });
                    } else if name.as_ref() == b"c" {
                        current_cell_col += 1;
                        current_cell_coord.clear();
                        current_cell_type = None;
                        current_cell_style = None;
                        v_content.clear();
                        f_content.clear();
                        is_content.clear();
                        f_type = None;
                        f_ref = None;
                        f_si = None;
                        in_v = false;
                        in_f = false;
                        in_is = false;
                        in_t = false;

                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"r" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    current_cell_coord.clear();
                                    current_cell_coord.push_str(s);
                                    current_cell_col = parse_col_from_ref(s);
                                }
                            } else if attr.key.as_ref() == b"t" {
                                current_cell_type = match attr.value.as_ref() {
                                    b"s" => Some("s".to_string()),
                                    b"inlineStr" => Some("inlineStr".to_string()),
                                    b"b" => Some("b".to_string()),
                                    b"e" => Some("e".to_string()),
                                    b"str" => Some("str".to_string()),
                                    other => std::str::from_utf8(other).ok().map(|s| s.to_string()),
                                };
                            } else if attr.key.as_ref() == b"s" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    current_cell_style = s.parse().ok();
                                }
                            }
                        }

                        if current_cell_coord.is_empty() {
                            current_cell_coord =
                                format!("{}{}", col_to_name(current_cell_col), current_row_num);
                        }
                    } else if name.as_ref() == b"f" {
                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"t" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    f_type = Some(s.to_string());
                                }
                            } else if attr.key.as_ref() == b"ref" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    f_ref = Some(s.to_string());
                                }
                            } else if attr.key.as_ref() == b"si" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    f_si = s.parse().ok();
                                }
                            }
                        }
                        if is_start {
                            in_f = true;
                            f_content.clear();
                        }
                    } else if name.as_ref() == b"v" {
                        in_v = true;
                        v_content.clear();
                    } else if name.as_ref() == b"is" {
                        in_is = true;
                        is_content.clear();
                    } else if name.as_ref() == b"t" {
                        in_t = true;
                    }
                }
                Ok(Event::Text(ref e)) => {
                    if in_v {
                        let s = e.unescape().map_err(RustParserError::Xml)?;
                        v_content.push_str(&s);
                    } else if in_f {
                        let s = e.unescape().map_err(RustParserError::Xml)?;
                        f_content.push_str(&s);
                    } else if in_is && in_t {
                        let s = e.unescape().map_err(RustParserError::Xml)?;
                        is_content.push_str(&s);
                    }
                }
                Ok(Event::End(ref e)) => {
                    let name = e.name();
                    if name.as_ref() == b"v" {
                        in_v = false;
                    } else if name.as_ref() == b"f" {
                        in_f = false;
                    } else if name.as_ref() == b"t" {
                        in_t = false;
                    } else if name.as_ref() == b"is" {
                        in_is = false;
                    } else if name.as_ref() == b"c" {
                        if let Some(ref mut row) = current_row {
                            let formula_opt = if f_content.is_empty() {
                                None
                            } else {
                                Some(std::mem::take(&mut f_content))
                            };

                            let resolved_f_type = if f_type.is_none() && f_si.is_some() {
                                Some("shared".to_string())
                            } else {
                                f_type.take()
                            };

                            let cell_val = match current_cell_type.as_deref() {
                                Some("s") => {
                                    if let Ok(idx) = v_content.trim().parse::<u32>() {
                                        let s = self.shared_strings.get_string(idx)?;
                                        CellValue::Text(s)
                                    } else {
                                        CellValue::Empty
                                    }
                                }
                                Some("inlineStr") => {
                                    validate_cell_string(&is_content)?;
                                    CellValue::Text(std::mem::take(&mut is_content))
                                }
                                Some("b") => {
                                    let trimmed = v_content.trim();
                                    let b_val =
                                        trimmed == "1" || trimmed.eq_ignore_ascii_case("true");
                                    CellValue::Bool(b_val)
                                }
                                Some("e") => CellValue::Error(std::mem::take(&mut v_content)),
                                Some("str") => {
                                    validate_cell_string(&v_content)?;
                                    CellValue::Text(std::mem::take(&mut v_content))
                                }
                                _ => {
                                    let trimmed = v_content.trim();
                                    if trimmed.is_empty() {
                                        CellValue::Empty
                                    } else {
                                        let is_date = current_cell_style
                                            .map(|s| self.styles.is_date_style(s))
                                            .unwrap_or(false);

                                        if is_date {
                                            if let Ok(num) = trimmed.parse::<f64>() {
                                                match parse_excel_serial(num, self.is_1904) {
                                                    Ok(dt) => CellValue::DateTime(dt),
                                                    Err(_) => CellValue::Float(num),
                                                }
                                            } else {
                                                validate_cell_string(trimmed)?;
                                                CellValue::Text(std::mem::take(&mut v_content))
                                            }
                                        } else if let Ok(int_val) = trimmed.parse::<i64>() {
                                            CellValue::Int(int_val)
                                        } else if let Ok(num) = trimmed.parse::<f64>() {
                                            if num.fract() == 0.0
                                                && num >= i64::MIN as f64
                                                && num <= i64::MAX as f64
                                            {
                                                CellValue::Int(num as i64)
                                            } else {
                                                CellValue::Float(num)
                                            }
                                        } else {
                                            validate_cell_string(trimmed)?;
                                            CellValue::Text(std::mem::take(&mut v_content))
                                        }
                                    }
                                }
                            };

                            row.cells.push(CellRecord {
                                col: current_cell_col,
                                coordinate: std::mem::take(&mut current_cell_coord),
                                cell_type: current_cell_type.take(),
                                value: cell_val,
                                formula: formula_opt,
                                formula_type: resolved_f_type,
                                formula_ref: f_ref.take(),
                                formula_si: f_si,
                            });
                        }
                    } else if name.as_ref() == b"row" {
                        if let Some(row) = current_row.take() {
                            last_row_cells = row.cells.len().max(8);
                            chunk.push(row);
                            self.processed_rows += 1;

                            if self.processed_rows.is_multiple_of(1_000) {
                                check_memory_guard()?;
                            }

                            if chunk.len() >= chunk_size {
                                return Ok(Some(chunk));
                            }
                        }
                    } else if name.as_ref() == b"worksheet" {
                        self.seen_worksheet_end = true;
                    }
                }
                Ok(Event::Eof) => {
                    if !self.seen_worksheet_end
                        || in_v
                        || in_f
                        || in_is
                        || in_t
                        || current_row.is_some()
                    {
                        return Err(RustParserError::CorruptWorkbook(
                            "Truncated XML stream: missing </worksheet> root closing tag"
                                .to_string(),
                        ));
                    }
                    if chunk.is_empty() {
                        return Ok(None);
                    } else {
                        return Ok(Some(chunk));
                    }
                }
                Err(e) => return Err(RustParserError::Xml(e)),
                _ => {}
            }
            buf.clear();
        }
    }
}

pub fn parse_col_from_ref(cell_ref: &str) -> u32 {
    let mut col: u32 = 0;
    for &b in cell_ref.as_bytes() {
        if b.is_ascii_alphabetic() {
            col = col * 26 + (b.to_ascii_uppercase() - b'A' + 1) as u32;
        } else {
            break;
        }
    }
    col
}

pub fn col_to_name(mut col: u32) -> String {
    if col == 0 {
        return "A".to_string();
    }
    let mut name = String::new();
    while col > 0 {
        col -= 1;
        name.push((b'A' + (col % 26) as u8) as char);
        col /= 26;
    }
    name.chars().rev().collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::shared_strings::SharedStringsTable;
    use crate::styles::StylesTable;
    use std::io::Cursor;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_col_coordinate_conversion() {
        assert_eq!(parse_col_from_ref("A1"), 1);
        assert_eq!(parse_col_from_ref("B10"), 2);
        assert_eq!(parse_col_from_ref("Z100"), 26);
        assert_eq!(parse_col_from_ref("AA1"), 27);
        assert_eq!(parse_col_from_ref("AZ1"), 52);
        assert_eq!(parse_col_from_ref("BA1"), 53);
        assert_eq!(parse_col_from_ref("XFD1048576"), 16384);
    }

    #[test]
    fn test_col_name_roundtrip() {
        assert_eq!(col_to_name(1), "A");
        assert_eq!(col_to_name(26), "Z");
        assert_eq!(col_to_name(27), "AA");
        assert_eq!(col_to_name(52), "AZ");
        assert_eq!(col_to_name(53), "BA");
        assert_eq!(col_to_name(16384), "XFD");

        for col in [1, 2, 26, 27, 52, 53, 702, 703, 16384] {
            let name = col_to_name(col);
            assert_eq!(parse_col_from_ref(&name), col);
        }
    }

    #[test]
    fn test_concurrent_independent_worksheet_streaming() {
        let xml_template = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
            <sheetData>
                <row r="1"><c r="A1"><v>100</v></c><c r="B1"><v>200</v></c></row>
                <row r="2"><c r="A2"><v>300</v></c><c r="B2"><v>400</v></c></row>
            </sheetData>
        </worksheet>"#;

        let sst = Arc::new(SharedStringsTable::new());
        let styles = Arc::new(StylesTable::default());

        let mut handles = Vec::new();
        for _ in 0..8 {
            let sst_clone = Arc::clone(&sst);
            let styles_clone = Arc::clone(&styles);
            let xml_data = xml_template.as_bytes().to_vec();

            handles.push(thread::spawn(move || {
                let cursor = Cursor::new(xml_data);
                let mut parser =
                    StreamingWorksheetParser::new(cursor, sst_clone, styles_clone, false);
                let chunk = parser.next_row_chunk(10).unwrap().unwrap();
                assert_eq!(chunk.len(), 2);
                assert_eq!(chunk[0].row, 1);
                assert_eq!(chunk[1].row, 2);
                assert_eq!(chunk[0].cells.len(), 2);
                assert_eq!(chunk[1].cells.len(), 2);
            }));
        }

        for h in handles {
            h.join().unwrap();
        }
    }
}
