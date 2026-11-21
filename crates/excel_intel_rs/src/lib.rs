pub mod cell_validator;
pub mod dates;
pub mod error;
pub mod memory_guard;
pub mod scratch;
pub mod shared_strings;
pub mod styles;
pub mod worksheet;
pub mod zip_handler;

use dates::parse_excel_serial as rs_parse_date;
use error::*;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use scratch::ScratchSpillFile;
use shared_strings::SharedStringsTable;
use styles::StylesTable;
use worksheet::{CellValue, StreamingWorksheetParser};
use zip_handler::ZipPackageReader;

use std::collections::HashMap;
use std::fs::File;
use std::io::{BufReader, Seek, SeekFrom};
use std::path::PathBuf;
use std::sync::Arc;

#[pyclass]
pub struct WorkbookStreamReader {
    path: PathBuf,
    sheet_names: Vec<String>,
    sheet_paths: HashMap<String, String>,
    shared_strings: Arc<SharedStringsTable>,
    styles: Arc<StylesTable>,
    is_1904: bool,
    has_macros: bool,
}

#[pymethods]
impl WorkbookStreamReader {
    #[new]
    pub fn new(path: String) -> PyResult<Self> {
        let path_buf = PathBuf::from(&path);
        let mut zip_pkg = ZipPackageReader::open(&path_buf)?;
        let has_macros = zip_pkg.has_macros();

        // 1. Read workbook properties and sheet catalog from xl/workbook.xml
        let workbook_xml = zip_pkg
            .read_file_to_string("xl/workbook.xml")?
            .ok_or_else(|| {
                RustParserError::CorruptWorkbook("Missing xl/workbook.xml".to_string())
            })?;

        let (sheet_names, sheet_rel_ids, is_1904) = parse_workbook_xml(&workbook_xml)?;

        // 2. Read relationships from xl/_rels/workbook.xml.rels
        let rels_xml = zip_pkg
            .read_file_to_string("xl/_rels/workbook.xml.rels")?
            .unwrap_or_default();
        let rel_target_map = parse_relationships_xml(&rels_xml);

        let mut sheet_paths = HashMap::new();
        for (idx, name) in sheet_names.iter().enumerate() {
            if let Some(r_id) = sheet_rel_ids.get(idx) {
                if let Some(target) = rel_target_map.get(r_id) {
                    let full_path = if target.starts_with('/') {
                        target.trim_start_matches('/').to_string()
                    } else {
                        format!("xl/{}", target)
                    };
                    sheet_paths.insert(name.clone(), full_path);
                }
            }
        }

        // 3. Read styles from xl/styles.xml
        let styles = if let Some(styles_xml) = zip_pkg.read_file_to_string("xl/styles.xml")? {
            Arc::new(StylesTable::parse(&styles_xml))
        } else {
            Arc::new(StylesTable::default())
        };

        // 4. Read shared strings from xl/sharedStrings.xml
        let mut sst = SharedStringsTable::new();
        if let Some(sst_xml) = zip_pkg.read_file_to_string("xl/sharedStrings.xml")? {
            populate_shared_strings(&sst_xml, &mut sst)?;
        }
        let shared_strings = Arc::new(sst);

        Ok(Self {
            path: path_buf,
            sheet_names,
            sheet_paths,
            shared_strings,
            styles,
            is_1904,
            has_macros,
        })
    }

    pub fn get_sheet_names(&self) -> Vec<String> {
        self.sheet_names.clone()
    }

    pub fn is_1904_system(&self) -> bool {
        self.is_1904
    }

    pub fn has_macros(&self) -> bool {
        self.has_macros
    }

    pub fn inspect(&self, py: Python<'_>) -> PyResult<PyObject> {
        let dict = PyDict::new_bound(py);
        dict.set_item("sheet_names", self.sheet_names.clone())?;
        dict.set_item("sheet_count", self.sheet_names.len())?;
        dict.set_item("is_1904", self.is_1904)?;
        dict.set_item("has_macros", self.has_macros)?;
        dict.set_item(
            "package_type",
            if self.has_macros { "xlsm" } else { "xlsx" },
        )?;
        dict.set_item("shared_strings_count", self.shared_strings.len())?;
        Ok(dict.into_py(py))
    }

    pub fn read_package_part(&self, part_name: &str) -> PyResult<Option<String>> {
        let mut zip_pkg = ZipPackageReader::open(&self.path)?;
        zip_pkg.read_file_to_string(part_name).map_err(|e| e.into())
    }

    pub fn list_package_parts(&self) -> PyResult<Vec<String>> {
        let zip_pkg = ZipPackageReader::open(&self.path)?;
        Ok(zip_pkg.file_names())
    }

    pub fn get_sheet_path(&self, sheet_name: &str) -> Option<String> {
        self.sheet_paths.get(sheet_name).cloned()
    }

    pub fn get_all_sheet_paths(&self) -> HashMap<String, String> {
        self.sheet_paths.clone()
    }

    #[pyo3(signature = (sheet_name_or_index, chunk_size = 1000))]
    pub fn stream_sheet(
        &self,
        _py: Python<'_>,
        sheet_name_or_index: &Bound<'_, PyAny>,
        chunk_size: usize,
    ) -> PyResult<SheetChunkIterator> {
        let sheet_name = if let Ok(idx) = sheet_name_or_index.extract::<usize>() {
            self.sheet_names.get(idx).cloned().ok_or_else(|| {
                RustParserError::CorruptWorkbook(format!("Sheet index {} out of range", idx))
            })?
        } else if let Ok(name) = sheet_name_or_index.extract::<String>() {
            name
        } else {
            return Err(
                RustParserError::CorruptWorkbook("Invalid sheet identifier".to_string()).into(),
            );
        };

        let sheet_path = self.sheet_paths.get(&sheet_name).ok_or_else(|| {
            RustParserError::CorruptWorkbook(format!(
                "Sheet '{}' target path not found",
                sheet_name
            ))
        })?;

        // Stream decompress sheet into bounded scratch file on local disk
        let mut scratch = ScratchSpillFile::new()?;
        let mut zip_pkg = ZipPackageReader::open(&self.path)?;
        zip_pkg.extract_file_to_scratch(sheet_path, &mut scratch.file)?;
        scratch.file.seek(SeekFrom::Start(0))?;

        let read_handle = scratch.file.try_clone().map_err(|e| {
            RustParserError::CorruptWorkbook(format!("Failed to clone scratch handle: {}", e))
        })?;
        let buf_reader = BufReader::with_capacity(256 * 1024, read_handle);

        let parser = StreamingWorksheetParser::new(
            buf_reader,
            Arc::clone(&self.shared_strings),
            Arc::clone(&self.styles),
            self.is_1904,
        );

        Ok(SheetChunkIterator {
            parser,
            _scratch: scratch,
            chunk_size,
        })
    }
}

#[pyclass]
pub struct SheetChunkIterator {
    parser: StreamingWorksheetParser<BufReader<File>>,
    _scratch: ScratchSpillFile,
    chunk_size: usize,
}

#[pymethods]
impl SheetChunkIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<PyObject>> {
        match self.parser.next_row_chunk(self.chunk_size)? {
            Some(rows) => {
                let k_row = pyo3::intern!(py, "row");
                let k_cells = pyo3::intern!(py, "cells");
                let k_col = pyo3::intern!(py, "col");
                let k_coordinate = pyo3::intern!(py, "coordinate");
                let k_cell_type = pyo3::intern!(py, "cell_type");
                let k_value = pyo3::intern!(py, "value");
                let k_formula = pyo3::intern!(py, "formula");
                let k_cached_value = pyo3::intern!(py, "cached_value");
                let k_formula_type = pyo3::intern!(py, "formula_type");
                let k_formula_ref = pyo3::intern!(py, "formula_ref");
                let k_formula_si = pyo3::intern!(py, "formula_si");
                let py_none = py.None();

                let mut py_rows = Vec::with_capacity(rows.len());
                for row in rows {
                    let row_dict = PyDict::new_bound(py);
                    row_dict.set_item(k_row, row.row)?;
                    let mut cells_list = Vec::with_capacity(row.cells.len());

                    for cell in row.cells {
                        let cell_dict = PyDict::new_bound(py);
                        cell_dict.set_item(k_col, cell.col)?;
                        cell_dict.set_item(k_coordinate, cell.coordinate)?;
                        if let Some(ref ct) = cell.cell_type {
                            cell_dict.set_item(k_cell_type, ct)?;
                        } else {
                            cell_dict.set_item(k_cell_type, &py_none)?;
                        }

                        let val_obj = match cell.value {
                            CellValue::Empty => py.None(),
                            CellValue::Text(s) => s.into_py(py),
                            CellValue::Int(i) => i.into_py(py),
                            CellValue::Float(f) => f.into_py(py),
                            CellValue::Bool(b) => b.into_py(py),
                            CellValue::DateTime(dt) => dt.into_py(py),
                            CellValue::Error(e) => e.into_py(py),
                        };
                        cell_dict.set_item(k_value, &val_obj)?;

                        let is_formula_cell = cell.formula.is_some()
                            || cell.formula_type.is_some()
                            || cell.formula_si.is_some();

                        if is_formula_cell {
                            if let Some(f) = cell.formula {
                                cell_dict.set_item(k_formula, f)?;
                            } else {
                                cell_dict.set_item(k_formula, &py_none)?;
                            }

                            cell_dict.set_item(k_cached_value, &val_obj)?;

                            if let Some(ft) = cell.formula_type {
                                cell_dict.set_item(k_formula_type, ft)?;
                            } else {
                                cell_dict.set_item(k_formula_type, &py_none)?;
                            }

                            if let Some(fr) = cell.formula_ref {
                                cell_dict.set_item(k_formula_ref, fr)?;
                            } else {
                                cell_dict.set_item(k_formula_ref, &py_none)?;
                            }

                            if let Some(si) = cell.formula_si {
                                cell_dict.set_item(k_formula_si, si)?;
                            } else {
                                cell_dict.set_item(k_formula_si, &py_none)?;
                            }
                        } else {
                            cell_dict.set_item(k_formula, &py_none)?;
                            cell_dict.set_item(k_cached_value, &py_none)?;
                            cell_dict.set_item(k_formula_type, &py_none)?;
                            cell_dict.set_item(k_formula_ref, &py_none)?;
                            cell_dict.set_item(k_formula_si, &py_none)?;
                        }

                        cells_list.push(cell_dict);
                    }
                    row_dict.set_item(k_cells, PyList::new_bound(py, cells_list))?;
                    py_rows.push(row_dict);
                }
                Ok(Some(PyList::new_bound(py, py_rows).into_py(py)))
            }
            None => Ok(None),
        }
    }
}

fn parse_workbook_xml(xml: &str) -> Result<(Vec<String>, Vec<String>, bool), RustParserError> {
    use quick_xml::events::Event;
    use quick_xml::Reader;

    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(true);

    let mut sheet_names = Vec::new();
    let mut sheet_rel_ids = Vec::new();
    let mut is_1904 = false;
    let mut buf = Vec::with_capacity(512);

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let name = e.name();
                if name.as_ref() == b"workbookPr" {
                    for attr in e.attributes().flatten() {
                        if attr.key.as_ref() == b"date1904" {
                            if let Ok(s) = std::str::from_utf8(&attr.value) {
                                is_1904 = s == "1" || s.eq_ignore_ascii_case("true");
                            }
                        }
                    }
                } else if name.as_ref() == b"sheet" {
                    let mut s_name: Option<String> = None;
                    let mut r_id: Option<String> = None;
                    for attr in e.attributes().flatten() {
                        if attr.key.as_ref() == b"name" {
                            if let Ok(s) = std::str::from_utf8(&attr.value) {
                                s_name = Some(s.to_string());
                            }
                        } else if attr.key.as_ref() == b"r:id" {
                            if let Ok(s) = std::str::from_utf8(&attr.value) {
                                r_id = Some(s.to_string());
                            }
                        }
                    }
                    if let (Some(n), Some(r)) = (s_name, r_id) {
                        sheet_names.push(n);
                        sheet_rel_ids.push(r);
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(RustParserError::Xml(e)),
            _ => {}
        }
        buf.clear();
    }

    Ok((sheet_names, sheet_rel_ids, is_1904))
}

fn parse_relationships_xml(xml: &str) -> HashMap<String, String> {
    use quick_xml::events::Event;
    use quick_xml::Reader;

    let mut reader = Reader::from_str(xml);
    let mut map = HashMap::new();
    let mut buf = Vec::with_capacity(512);

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                if e.name().as_ref() == b"Relationship" {
                    let mut id: Option<String> = None;
                    let mut target: Option<String> = None;
                    for attr in e.attributes().flatten() {
                        if attr.key.as_ref() == b"Id" {
                            if let Ok(s) = std::str::from_utf8(&attr.value) {
                                id = Some(s.to_string());
                            }
                        } else if attr.key.as_ref() == b"Target" {
                            if let Ok(s) = std::str::from_utf8(&attr.value) {
                                target = Some(s.to_string());
                            }
                        }
                    }
                    if let (Some(i), Some(t)) = (id, target) {
                        map.insert(i, t);
                    }
                }
            }
            Ok(Event::Eof) => break,
            _ => {}
        }
        buf.clear();
    }

    map
}

fn populate_shared_strings(xml: &str, sst: &mut SharedStringsTable) -> Result<(), RustParserError> {
    use quick_xml::events::Event;
    use quick_xml::Reader;

    let mut reader = Reader::from_str(xml);
    let mut in_si = false;
    let mut in_t = false;
    let mut current_string = String::new();
    let mut buf = Vec::with_capacity(512);

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                let name = e.name();
                if name.as_ref() == b"si" {
                    in_si = true;
                    current_string.clear();
                } else if name.as_ref() == b"t" {
                    in_t = true;
                }
            }
            Ok(Event::Text(ref e)) => {
                if in_t && in_si {
                    if let Ok(s) = e.unescape() {
                        current_string.push_str(&s);
                    }
                }
            }
            Ok(Event::End(ref e)) => {
                let name = e.name();
                if name.as_ref() == b"t" {
                    in_t = false;
                } else if name.as_ref() == b"si" {
                    in_si = false;
                    sst.push_string(&current_string)?;
                    current_string.clear();
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(RustParserError::Xml(e)),
            _ => {}
        }
        buf.clear();
    }

    Ok(())
}

#[pyfunction]
#[pyo3(signature = (serial, is_1904 = false))]
pub fn py_parse_excel_serial(py: Python<'_>, serial: f64, is_1904: bool) -> PyResult<PyObject> {
    let dt = rs_parse_date(serial, is_1904)?;
    Ok(dt.into_py(py))
}

#[pyfunction]
pub fn py_validate_cell_string(s: &str) -> PyResult<()> {
    cell_validator::validate_cell_string(s)?;
    Ok(())
}

#[pyfunction]
pub fn py_get_process_working_set_bytes() -> usize {
    memory_guard::get_current_working_set_bytes()
}

#[pyfunction]
pub fn py_check_memory_guard() -> PyResult<()> {
    memory_guard::check_memory_guard()?;
    Ok(())
}

#[pyfunction]
pub fn py_scavenge_scratch_dir() -> PyResult<usize> {
    let cleaned = scratch::scavenge_scratch_dir()?;
    Ok(cleaned)
}

#[pymodule]
fn _rs(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<WorkbookStreamReader>()?;
    m.add_class::<SheetChunkIterator>()?;
    m.add_function(wrap_pyfunction!(py_parse_excel_serial, m)?)?;
    m.add_function(wrap_pyfunction!(py_validate_cell_string, m)?)?;
    m.add_function(wrap_pyfunction!(py_get_process_working_set_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(py_check_memory_guard, m)?)?;
    m.add_function(wrap_pyfunction!(py_scavenge_scratch_dir, m)?)?;

    m.add("ParserError", py.get_type_bound::<ParserError>())?;
    m.add(
        "PlatformResourceLimitError",
        py.get_type_bound::<PlatformResourceLimitError>(),
    )?;
    m.add(
        "DateOutOfRangeError",
        py.get_type_bound::<DateOutOfRangeError>(),
    )?;
    m.add(
        "CorruptWorkbookError",
        py.get_type_bound::<CorruptWorkbookError>(),
    )?;
    m.add(
        "UnsupportedFormatError",
        py.get_type_bound::<UnsupportedFormatError>(),
    )?;

    Ok(())
}
