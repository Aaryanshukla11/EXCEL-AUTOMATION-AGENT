use quick_xml::events::Event;
use quick_xml::Reader;

#[derive(Default, Debug)]
pub struct StylesTable {
    cell_xfs_is_date: Vec<bool>,
    custom_date_formats: hashbrown::HashSet<u32>,
}

impl StylesTable {
    pub fn parse(xml_content: &str) -> Self {
        let mut table = StylesTable::default();
        let mut reader = Reader::from_str(xml_content);
        reader.config_mut().trim_text(true);

        let mut in_num_fmts = false;
        let mut in_cell_xfs = false;

        let mut buf = Vec::with_capacity(512);

        loop {
            match reader.read_event_into(&mut buf) {
                Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                    let name = e.name();
                    if name.as_ref() == b"numFmts" {
                        in_num_fmts = true;
                    } else if name.as_ref() == b"cellXfs" {
                        in_cell_xfs = true;
                    } else if in_num_fmts && name.as_ref() == b"numFmt" {
                        let mut num_fmt_id: Option<u32> = None;
                        let mut format_code: Option<String> = None;
                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"numFmtId" {
                                if let Ok(val_str) = std::str::from_utf8(&attr.value) {
                                    num_fmt_id = val_str.parse().ok();
                                }
                            } else if attr.key.as_ref() == b"formatCode" {
                                if let Ok(val_str) = std::str::from_utf8(&attr.value) {
                                    format_code = Some(val_str.to_lowercase());
                                }
                            }
                        }
                        if let (Some(id), Some(code)) = (num_fmt_id, format_code) {
                            if is_date_format_code(&code) {
                                table.custom_date_formats.insert(id);
                            }
                        }
                    } else if in_cell_xfs && name.as_ref() == b"xf" {
                        let mut num_fmt_id: u32 = 0;
                        for attr in e.attributes().flatten() {
                            if attr.key.as_ref() == b"numFmtId" {
                                if let Ok(val_str) = std::str::from_utf8(&attr.value) {
                                    num_fmt_id = val_str.parse().unwrap_or(0);
                                }
                            }
                        }
                        let is_date = is_builtin_date_id(num_fmt_id)
                            || table.custom_date_formats.contains(&num_fmt_id);
                        table.cell_xfs_is_date.push(is_date);
                    }
                }
                Ok(Event::End(ref e)) => {
                    let name = e.name();
                    if name.as_ref() == b"numFmts" {
                        in_num_fmts = false;
                    } else if name.as_ref() == b"cellXfs" {
                        in_cell_xfs = false;
                    }
                }
                Ok(Event::Eof) => break,
                Err(_) => break,
                _ => {}
            }
            buf.clear();
        }

        table
    }

    pub fn is_date_style(&self, style_idx: usize) -> bool {
        self.cell_xfs_is_date
            .get(style_idx)
            .copied()
            .unwrap_or(false)
    }
}

fn is_builtin_date_id(id: u32) -> bool {
    // Standard OpenXML date/time builtins
    matches!(id, 14..=22 | 45..=47)
}

fn is_date_format_code(code: &str) -> bool {
    // Heuristic: check if format string contains date/time tokens
    // Ignore quoted literals and bracketed color/locale tags
    let mut stripped = String::with_capacity(code.len());
    let mut in_quotes = false;
    let mut in_brackets = false;

    for c in code.chars() {
        if c == '"' {
            in_quotes = !in_quotes;
        } else if c == '[' {
            in_brackets = true;
        } else if c == ']' {
            in_brackets = false;
        } else if !in_quotes && !in_brackets {
            stripped.push(c);
        }
    }

    stripped.contains('y')
        || stripped.contains('m')
        || stripped.contains('d')
        || stripped.contains('h')
        || stripped.contains('s')
}
