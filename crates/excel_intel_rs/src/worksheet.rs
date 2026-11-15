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
                            cells: Vec::new(),
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
                                    current_cell_coord = s.to_string();
                                    current_cell_col = parse_col_from_ref(s);
                                }
                            } else if attr.key.as_ref() == b"t" {
                                if let Ok(s) = std::str::from_utf8(&attr.value) {
                                    current_cell_type = Some(s.to_string());
                                }
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
                                Some(f_content.clone())
                            };

                            let resolved_f_type = if f_type.is_none() && f_si.is_some() {
                                Some("shared".to_string())
                            } else {
                                f_type.clone()
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
                                    CellValue::Text(is_content.clone())
                                }
                                Some("b") => {
                                    let trimmed = v_content.trim();
                                    let b_val =
                                        trimmed == "1" || trimmed.eq_ignore_ascii_case("true");
                                    CellValue::Bool(b_val)
                                }
                                Some("e") => CellValue::Error(v_content.trim().to_string()),
                                Some("str") => {
                                    validate_cell_string(&v_content)?;
                                    CellValue::Text(v_content.clone())
                                }
                                _ => {
                                    let trimmed = v_content.trim();
                                    if trimmed.is_empty() {
                                        CellValue::Empty
                                    } else if let Ok(num) = trimmed.parse::<f64>() {
                                        let is_date = current_cell_style
                                            .map(|s| self.styles.is_date_style(s))
                                            .unwrap_or(false);

                                        if is_date {
                                            match parse_excel_serial(num, self.is_1904) {
                                                Ok(dt) => CellValue::DateTime(dt),
                                                Err(_) => CellValue::Float(num),
                                            }
                                        } else if num.fract() == 0.0
                                            && num >= i64::MIN as f64
                                            && num <= i64::MAX as f64
                                        {
                                            CellValue::Int(num as i64)
                                        } else {
                                            CellValue::Float(num)
                                        }
                                    } else {
                                        validate_cell_string(trimmed)?;
                                        CellValue::Text(trimmed.to_string())
                                    }
                                }
                            };

                            row.cells.push(CellRecord {
                                col: current_cell_col,
                                coordinate: current_cell_coord.clone(),
                                cell_type: current_cell_type.clone(),
                                value: cell_val,
                                formula: formula_opt,
                                formula_type: resolved_f_type,
                                formula_ref: f_ref.clone(),
                                formula_si: f_si,
                            });
                        }
                    } else if name.as_ref() == b"row" {
                        if let Some(row) = current_row.take() {
                            chunk.push(row);
                            self.processed_rows += 1;

                            if self.processed_rows.is_multiple_of(10_000) {
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
    for c in cell_ref.chars() {
        if c.is_ascii_alphabetic() {
            col = col * 26 + (c.to_ascii_uppercase() as u32 - 'A' as u32 + 1);
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
