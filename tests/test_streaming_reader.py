"""Tests for StreamingWorkbookReader (M02 Sprint 1 & Defect Closure).

Validates:
- Valid XLSX & XLSM package inspection and streaming.
- Package entry validation and missing entry rejection.
- Corrupt ZIP and unsupported OLE/Compound File rejection.
- Structural ZIP64 rejection (validated against EOCD; avoids false positives from comments/payloads).
- Decompression quota and compression-ratio tripwire (activating only >10 MB).
- Malformed XML and truncated XML stream handling.
- Sparse worksheets with non-consecutive rows and columns.
- Dedicated inline strings (<is><t>) and shared-string references (<v>) extraction.
- Oversized cell text rejection: 32,767 UTF-16 units pass; 32,768 and >131,072 bytes rejected.
- Temporary scratch resource cleanup after parser failures.
- Encrypted workbook rejection.
- Formula text and cached-value separation.
- Shared formula metadata (<f t="shared">) capture without AST expansion.
Built with 100% standard library (zipfile/xml) - zero external generator dependencies.
"""

import datetime
from pathlib import Path
import struct
import tempfile
import zipfile
import pytest

from excel_intel.core.parser import (
    CorruptWorkbookError,
    PlatformResourceLimitError,
    StreamingWorkbookReader,
    UnsupportedFormatError,
)


def create_minimal_xlsx(path: Path) -> None:
    """Generate a clean, valid OpenXML workbook fixture using python stdlib zipfile."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStringTable+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<workbookPr date1904="0"/>'
        '<sheets>'
        '<sheet name="DataSheet" sheetId="1" r:id="rId1"/>'
        '<sheet name="LookupSheet" sheetId="2" r:id="rId2"/>'
        '</sheets>'
        '</workbook>'
    )

    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '</cellXfs>'
        '</styleSheet>'
    )

    shared_strings = [
        "ID", "Name", "Score", "Active", "CreatedDate", "Calculated",
        "Alpha", "Beta", "Key", "Value", "K1", "V1"
    ]
    sst_entries = "".join(f"<si><t>{s}</t></si>" for s in shared_strings)
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        f'{sst_entries}'
        '</sst>'
    )

    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c>'
        '<c r="E1" t="s"><v>4</v></c>'
        '<c r="F1" t="s"><v>5</v></c>'
        '</row>'
        '<row r="2">'
        '<c r="A2"><v>1</v></c>'
        '<c r="B2" t="s"><v>6</v></c>'
        '<c r="C2"><v>95.5</v></c>'
        '<c r="D2" t="b"><v>1</v></c>'
        '<c r="E2" s="1"><v>45458</v></c>'
        '<c r="F2"><f>C2*1.1</f><v>105.05</v></c>'
        '</row>'
        '<row r="3">'
        '<c r="A3"><v>2</v></c>'
        '<c r="B3" t="s"><v>7</v></c>'
        '<c r="C3"><v>82</v></c>'
        '<c r="D3" t="b"><v>0</v></c>'
        '<c r="E3" t="inlineStr"><is><t>InlineTest</t></is></c>'
        '</row>'
        '</sheetData>'
        '</worksheet>'
    )

    sheet2_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        '<row r="1"><c r="A1" t="s"><v>8</v></c><c r="B1" t="s"><v>9</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>10</v></c><c r="B2" t="s"><v>11</v></c></row>'
        '</sheetData>'
        '</worksheet>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles_xml)
        z.writestr("xl/sharedStrings.xml", sst_xml)
        z.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        z.writestr("xl/worksheets/sheet2.xml", sheet2_xml)


@pytest.fixture
def sample_workbook(tmp_path: Path) -> Path:
    wb_path = tmp_path / "test_sample.xlsx"
    create_minimal_xlsx(wb_path)
    return wb_path


class TestStreamingWorkbookReader:
    """End-to-end streaming reader tests."""

    def test_open_and_sheet_metadata(self, sample_workbook: Path) -> None:
        reader = StreamingWorkbookReader(sample_workbook)
        assert reader.sheet_names == ["DataSheet", "LookupSheet"]
        assert reader.is_1904 is False
        assert reader.package_type == "xlsx"
        assert reader.has_macros is False

        info = reader.inspect()
        assert info["sheet_names"] == ["DataSheet", "LookupSheet"]
        assert info["sheet_count"] == 2
        assert info["package_type"] == "xlsx"
        assert info["has_macros"] is False
        assert info["shared_strings_count"] == 12

    def test_stream_sheet_data(self, sample_workbook: Path) -> None:
        reader = StreamingWorkbookReader(sample_workbook)
        chunks = list(reader.stream_sheet("DataSheet", chunk_size=2))

        assert len(chunks) == 2
        chunk1 = chunks[0]
        assert len(chunk1) == 2

        # Row 1 (Headers)
        row1 = chunk1[0]
        assert row1["row"] == 1
        headers = [c["value"] for c in row1["cells"]]
        assert headers == ["ID", "Name", "Score", "Active", "CreatedDate", "Calculated"]

        # Row 2 (Data)
        row2 = chunk1[1]
        assert row2["row"] == 2
        cells = row2["cells"]
        assert cells[0]["value"] == 1
        assert cells[0]["coordinate"] == "A2"
        assert cells[1]["value"] == "Alpha"
        assert cells[1]["coordinate"] == "B2"
        assert cells[2]["value"] == 95.5
        assert cells[3]["value"] is True
        # Date column: serial 45458 = 2024-06-15
        assert isinstance(cells[4]["value"], datetime.date)
        assert cells[4]["value"] == datetime.date(2024, 6, 15)
        # Formula column
        assert cells[5]["formula"] == "C2*1.1"
        assert cells[5]["cached_value"] == 105.05
        assert cells[5]["value"] == 105.05

        # Row 3 (InlineStr and bool)
        chunk2 = chunks[1]
        assert len(chunk2) == 1
        row3 = chunk2[0]
        assert row3["row"] == 3
        cells3 = row3["cells"]
        assert cells3[0]["value"] == 2
        assert cells3[1]["value"] == "Beta"
        assert cells3[2]["value"] == 82
        assert cells3[3]["value"] is False
        assert cells3[4]["value"] == "InlineTest"
        assert cells3[4]["cell_type"] == "inlineStr"

    def test_stream_second_sheet(self, sample_workbook: Path) -> None:
        reader = StreamingWorkbookReader(sample_workbook)
        chunks = list(reader.stream_sheet(1, chunk_size=10))
        assert len(chunks) == 1
        rows = chunks[0]
        assert len(rows) == 2
        assert rows[0]["cells"][0]["value"] == "Key"
        assert rows[1]["cells"][0]["value"] == "K1"
        assert rows[1]["cells"][1]["value"] == "V1"

    def test_valid_xlsm_package_inspection(self, tmp_path: Path) -> None:
        """Verify XLSM workbooks with VBA project binaries are recognized correctly."""
        xlsm_path = tmp_path / "macro_test.xlsm"
        create_minimal_xlsx(xlsm_path)

        with zipfile.ZipFile(xlsm_path, "a", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("xl/vbaProject.bin", b"\xD0\xCF\x11\xE0dummy_vba_binary_data")

        reader = StreamingWorkbookReader(xlsm_path)
        assert reader.has_macros is True
        assert reader.package_type == "xlsm"

        info = reader.inspect()
        assert info["package_type"] == "xlsm"
        assert info["has_macros"] is True

        chunks = list(reader.stream_sheet("DataSheet", chunk_size=10))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_missing_content_types_rejection(self, tmp_path: Path) -> None:
        path = tmp_path / "missing_types.xlsx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("xl/workbook.xml", "<workbook/>")

        with pytest.raises(CorruptWorkbookError) as exc_info:
            StreamingWorkbookReader(path)
        assert "[Content_Types].xml" in str(exc_info.value)

    def test_missing_workbook_xml_rejection(self, tmp_path: Path) -> None:
        path = tmp_path / "missing_wb.xlsx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")

        with pytest.raises(CorruptWorkbookError) as exc_info:
            StreamingWorkbookReader(path)
        assert "xl/workbook.xml" in str(exc_info.value)

    def test_ole_compound_file_rejection(self, tmp_path: Path) -> None:
        ole_path = tmp_path / "legacy.xls"
        ole_header = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + b"\x00" * 504
        ole_path.write_bytes(ole_header)

        with pytest.raises(UnsupportedFormatError) as exc_info:
            StreamingWorkbookReader(ole_path)
        assert "Unsupported OLE" in str(exc_info.value)

    def test_corrupt_file_rejection(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / "corrupt.xlsx"
        corrupt_path.write_bytes(b"NOT_A_VALID_ZIP_PACKAGE_DATA_HERE")

        with pytest.raises(CorruptWorkbookError):
            StreamingWorkbookReader(corrupt_path)

    def test_genuine_zip64_rejection(self, tmp_path: Path) -> None:
        """Verify that genuine ZIP64 archives with valid locator and EOCD are rejected."""
        zip64_path = tmp_path / "genuine_zip64.xlsx"
        create_minimal_xlsx(zip64_path)

        data = bytearray(zip64_path.read_bytes())
        eocd_idx = data.rfind(b"\x50\x4b\x05\x06")
        cd_data = data[:eocd_idx]

        zip64_eocd_offset = len(cd_data)
        # 1. Zip64 EOCD record (56 bytes: 4 sig + 8 size + 44 payload)
        zip64_eocd = b"\x50\x4b\x06\x06" + struct.pack("<QHHIIQQQQ", 44, 45, 45, 0, 0, 10, 10, 1000, 0)
        # 2. Zip64 locator (20 bytes: 4 sig + 4 disk_start + 8 offset + 4 total_disks)
        zip64_locator = b"\x50\x4b\x06\x07" + struct.pack("<IQI", 0, zip64_eocd_offset, 1)
        # 3. Standard EOCD (22 bytes with 0xFFFF / 0xFFFFFFFF overflow indicators)
        standard_eocd = b"\x50\x4b\x05\x06" + struct.pack("<HHHHIIH", 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)

        zip64_path.write_bytes(cd_data + zip64_eocd + zip64_locator + standard_eocd)

        with pytest.raises(PlatformResourceLimitError) as exc_info:
            StreamingWorkbookReader(zip64_path)
        assert "ZIP64" in str(exc_info.value)

    def test_zip64_detection_regression_comment_false_positive(self, tmp_path: Path) -> None:
        """Verify that a ZIP comment containing ZIP64 signatures does NOT cause false rejection."""
        wb_path = tmp_path / "comment_fake_zip64.xlsx"
        create_minimal_xlsx(wb_path)

        # Inject raw ZIP64 signatures inside the archive comment
        comment_payload = b"Benign comment containing \x50\x4b\x06\x07 and \x50\x4b\x06\x06 signatures"
        with zipfile.ZipFile(wb_path, "a") as z:
            z.comment = comment_payload

        reader = StreamingWorkbookReader(wb_path)
        assert reader.sheet_names == ["DataSheet", "LookupSheet"]
        chunks = list(reader.stream_sheet(0, chunk_size=2))
        assert len(chunks) == 2
        assert chunks[0][0]["row"] == 1

    def test_zip64_detection_regression_payload_false_positive(self, tmp_path: Path) -> None:
        """Verify that cell text containing literal ZIP64 signatures does NOT cause false rejection."""
        wb_path = tmp_path / "payload_fake_zip64.xlsx"
        create_minimal_xlsx(wb_path)

        fake_sig_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1" t="inlineStr"><is><t>PK\x06\x07_FAKE_ZIP64_LOCATOR_IN_CELL</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>PK\x06\x06_FAKE_ZIP64_EOCD_IN_CELL</t></is></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", fake_sig_sheet)

        reader = StreamingWorkbookReader(wb_path)
        chunks = list(reader.stream_sheet(0))
        assert len(chunks) == 1
        cells = chunks[0][0]["cells"]
        assert "PK\x06\x07" in cells[0]["value"]
        assert "PK\x06\x06" in cells[1]["value"]

    def test_encrypted_workbook_rejection(self, tmp_path: Path) -> None:
        """Verify password-encrypted or encrypted packages are rejected with UnsupportedFormatError."""
        enc_path = tmp_path / "encrypted.xlsx"
        create_minimal_xlsx(enc_path)

        data = bytearray(enc_path.read_bytes())
        # Set bit 0 (encryption flag) in first local file header (offset 6)
        loc_idx = data.find(b"\x50\x4b\x03\x04")
        if loc_idx != -1:
            data[loc_idx + 6] |= 0x01
        # Set bit 0 in central directory entry (offset 8)
        cd_idx = data.find(b"\x50\x4b\x01\x02")
        if cd_idx != -1:
            data[cd_idx + 8] |= 0x01

        enc_path.write_bytes(bytes(data))

        with pytest.raises(UnsupportedFormatError) as exc_info:
            StreamingWorkbookReader(enc_path)
        assert "encrypted" in str(exc_info.value).lower()

    def test_compression_ratio_tripwire_threshold(self, tmp_path: Path) -> None:
        """Verify compression ratio tripwire only trips when output EXCEEDS 10.0 MB threshold."""
        # 1. 5 MB output (high ratio >100x, but output <= 10 MB) -> MUST PASS
        pass_path = tmp_path / "ratio_5mb.xlsx"
        create_minimal_xlsx(pass_path)
        sheet_5mb = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'<!-- {" " * 5_000_000} -->'
            '<row r="1"><c r="A1"><v>42</v></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        with zipfile.ZipFile(pass_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", sheet_5mb)

        reader_5mb = StreamingWorkbookReader(pass_path)
        chunks = list(reader_5mb.stream_sheet(0))
        assert len(chunks) == 1
        assert chunks[0][0]["cells"][0]["value"] == 42

        # 2. 15 MB output (high ratio > 100x and output > 10 MB) -> MUST FAIL with ERR_ZIP_DECOMPRESSION_BOMB
        fail_path = tmp_path / "ratio_15mb.xlsx"
        create_minimal_xlsx(fail_path)
        sheet_15mb = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'<!-- {" " * 15_000_000} -->'
            '<row r="1"><c r="A1"><v>42</v></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        with zipfile.ZipFile(fail_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", sheet_15mb)

        reader_15mb = StreamingWorkbookReader(fail_path)
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            list(reader_15mb.stream_sheet(0))
        assert "ERR_ZIP_DECOMPRESSION_BOMB" in str(exc_info.value) or "ratio" in str(exc_info.value).lower()

    def test_oversized_cell_text_rejection_boundaries(self, tmp_path: Path) -> None:
        """Verify 32,767 UTF-16 code units pass, while 32,768 and >131,072 bytes are rejected."""
        # 1. 32,767 ASCII characters -> PASS
        pass_path = tmp_path / "cell_len_pass.xlsx"
        create_minimal_xlsx(pass_path)
        pass_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'<row r="1"><c r="A1" t="inlineStr"><is><t>{"a" * 32_767}</t></is></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        with zipfile.ZipFile(pass_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", pass_sheet)

        reader_pass = StreamingWorkbookReader(pass_path)
        chunks = list(reader_pass.stream_sheet(0))
        assert len(chunks[0][0]["cells"][0]["value"]) == 32_767

        # 2. 32,768 ASCII characters (> 32,767 UTF-16 limit) -> REJECT
        fail_path = tmp_path / "cell_len_fail.xlsx"
        create_minimal_xlsx(fail_path)
        fail_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'<row r="1"><c r="A1" t="inlineStr"><is><t>{"a" * 32_768}</t></is></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        with zipfile.ZipFile(fail_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", fail_sheet)

        reader_fail = StreamingWorkbookReader(fail_path)
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            list(reader_fail.stream_sheet(0))
        assert "32,767" in str(exc_info.value) or "UTF-16" in str(exc_info.value)

        # 3. 131,073 bytes (> 131,072 safety buffer limit) -> REJECT
        byte_fail_path = tmp_path / "byte_len_fail.xlsx"
        create_minimal_xlsx(byte_fail_path)
        byte_fail_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            f'<row r="1"><c r="A1" t="inlineStr"><is><t>{"a" * 131_073}</t></is></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        with zipfile.ZipFile(byte_fail_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", byte_fail_sheet)

        reader_byte_fail = StreamingWorkbookReader(byte_fail_path)
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            list(reader_byte_fail.stream_sheet(0))
        assert "131,072" in str(exc_info.value) or "safety" in str(exc_info.value).lower()

    def test_resource_cleanup_after_parser_failure(self, tmp_path: Path) -> None:
        """Verify temporary scratch files are cleanly removed upon parser failure."""
        scratch_dir = Path(tempfile.gettempdir()) / "excel_intel_scratch"
        existing_files = set(scratch_dir.glob("*")) if scratch_dir.exists() else set()

        bad_xml_path = tmp_path / "bad_xml_cleanup.xlsx"
        create_minimal_xlsx(bad_xml_path)
        with zipfile.ZipFile(bad_xml_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet><sheetData><row r="1"><c r="A1"><v>1</c></v></row></sheetData></worksheet>')

        try:
            reader = StreamingWorkbookReader(bad_xml_path)
            list(reader.stream_sheet(0))
        except CorruptWorkbookError:
            pass

        current_files = set(scratch_dir.glob("*")) if scratch_dir.exists() else set()
        new_leaked_files = current_files - existing_files
        assert len(new_leaked_files) == 0, f"Leaked temporary scratch files: {new_leaked_files}"

    def test_dedicated_inline_string_and_shared_string_lookup(self, tmp_path: Path) -> None:
        """Dedicated test for inline string and shared-string lookup extraction."""
        path = tmp_path / "strings_dedicated.xlsx"
        create_minimal_xlsx(path)

        strings_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1" t="inlineStr"><is><t>Dedicated Inline Text</t></is></c>'
            '<c r="B1" t="s"><v>6</v></c>'  # Shared string index 6 = "Alpha"
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>0</t></si><si><t>1</t></si><si><t>2</t></si><si><t>3</t></si><si><t>4</t></si><si><t>5</t></si><si><t>Alpha</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", strings_sheet)

        reader = StreamingWorkbookReader(path)
        chunks = list(reader.stream_sheet(0))
        cells = chunks[0][0]["cells"]

        # Inline string cell
        assert cells[0]["coordinate"] == "A1"
        assert cells[0]["cell_type"] == "inlineStr"
        assert cells[0]["value"] == "Dedicated Inline Text"

        # Shared string cell
        assert cells[1]["coordinate"] == "B1"
        assert cells[1]["cell_type"] == "s"
        assert cells[1]["value"] == "Alpha"

    def test_formula_cached_value_separation_independent(self, tmp_path: Path) -> None:
        """Independent verification of formula text, cached values, and shared formulas."""
        path = tmp_path / "formula_cached.xlsx"
        create_minimal_xlsx(path)

        formula_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1"><f>A2+A3</f><v>100</v></c>'
            '<c r="A2"><v>50</v></c>'
            '</row>'
            '<row r="2">'
            '<c r="B1"><f t="shared" ref="B1:B2" si="0">C1*2</f><v>200</v></c>'
            '<c r="B2"><f t="shared" si="0"/><v>300</v></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", formula_sheet)

        reader = StreamingWorkbookReader(path)
        chunks = list(reader.stream_sheet(0))
        rows = chunks[0]

        # Normal formula cell A1
        cell_a1 = rows[0]["cells"][0]
        assert cell_a1["coordinate"] == "A1"
        assert cell_a1["formula"] == "A2+A3"
        assert cell_a1["cached_value"] == 100
        assert cell_a1["value"] == 100

        # Non-formula cell A2
        cell_a2 = rows[0]["cells"][1]
        assert cell_a2["coordinate"] == "A2"
        assert cell_a2["formula"] is None
        assert cell_a2["cached_value"] is None
        assert cell_a2["value"] == 50

        # Shared formula master cell B1
        cell_b1 = rows[1]["cells"][0]
        assert cell_b1["coordinate"] == "B1"
        assert cell_b1["formula"] == "C1*2"
        assert cell_b1["formula_type"] == "shared"
        assert cell_b1["cached_value"] == 200
        assert cell_b1["value"] == 200

        # Shared formula follower cell B2
        cell_b2 = rows[1]["cells"][1]
        assert cell_b2["coordinate"] == "B2"
        assert cell_b2["formula"] is None
        assert cell_b2["formula_type"] == "shared"
        assert cell_b2["cached_value"] == 300
        assert cell_b2["value"] == 300

    def test_malformed_xml_rejection(self, tmp_path: Path) -> None:
        """Verify mismatched/unclosed XML tags in worksheet produce CorruptWorkbookError."""
        bad_xml_path = tmp_path / "bad_xml.xlsx"
        create_minimal_xlsx(bad_xml_path)

        malformed_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1"><c r="A1"><v>100</c></v></row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(bad_xml_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", malformed_sheet)

        reader = StreamingWorkbookReader(bad_xml_path)
        with pytest.raises(CorruptWorkbookError):
            list(reader.stream_sheet(0))

    def test_truncated_xml_rejection(self, tmp_path: Path) -> None:
        """Verify truncated XML stream produces CorruptWorkbookError."""
        trunc_path = tmp_path / "truncated.xlsx"
        create_minimal_xlsx(trunc_path)

        truncated_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1"><c r="A1"><v>42'
        )

        with zipfile.ZipFile(trunc_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", truncated_sheet)

        reader = StreamingWorkbookReader(trunc_path)
        with pytest.raises(CorruptWorkbookError):
            list(reader.stream_sheet(0))

    def test_sparse_worksheet_coordinates(self, tmp_path: Path) -> None:
        """Verify non-consecutive rows and columns preserve exact sparse coordinates without phantoms."""
        sparse_path = tmp_path / "sparse.xlsx"
        create_minimal_xlsx(sparse_path)

        sparse_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1"><v>10</v></c>'
            '<c r="Z1"><v>20</v></c>'
            '</row>'
            '<row r="10">'
            '<c r="B10"><v>100</v></c>'
            '</row>'
            '<row r="50">'
            '<c r="AA50"><v>500</v></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(sparse_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Sparse" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", sparse_sheet)

        reader = StreamingWorkbookReader(sparse_path)
        chunks = list(reader.stream_sheet(0, chunk_size=10))
        assert len(chunks) == 1
        rows = chunks[0]

        assert len(rows) == 3
        assert rows[0]["row"] == 1
        assert rows[1]["row"] == 10
        assert rows[2]["row"] == 50

        r1_cells = rows[0]["cells"]
        assert len(r1_cells) == 2
        assert r1_cells[0]["col"] == 1
        assert r1_cells[0]["coordinate"] == "A1"
        assert r1_cells[0]["value"] == 10
        assert r1_cells[1]["col"] == 26
        assert r1_cells[1]["coordinate"] == "Z1"
        assert r1_cells[1]["value"] == 20

        assert len(rows[1]["cells"]) == 1
        assert rows[1]["cells"][0]["col"] == 2
        assert rows[1]["cells"][0]["coordinate"] == "B10"
        assert rows[1]["cells"][0]["value"] == 100

        assert len(rows[2]["cells"]) == 1
        assert rows[2]["cells"][0]["col"] == 27
        assert rows[2]["cells"][0]["coordinate"] == "AA50"
        assert rows[2]["cells"][0]["value"] == 500

    def test_shared_formula_metadata_without_ast_expansion(self, tmp_path: Path) -> None:
        """Verify shared formula group metadata is captured accurately without AST expansion."""
        shared_f_path = tmp_path / "shared_formula.xlsx"
        create_minimal_xlsx(shared_f_path)

        shared_f_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1"><f t="shared" ref="A1:A5" si="0">B1+C1</f><v>10</v></c>'
            '</row>'
            '<row r="2">'
            '<c r="A2"><f t="shared" si="0"/><v>20</v></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(shared_f_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="SharedF" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", shared_f_sheet)

        reader = StreamingWorkbookReader(shared_f_path)
        chunks = list(reader.stream_sheet(0))
        assert len(chunks) == 1
        rows = chunks[0]
        assert len(rows) == 2

        # Master cell A1
        cell_a1 = rows[0]["cells"][0]
        assert cell_a1["coordinate"] == "A1"
        assert cell_a1["formula"] == "B1+C1"
        assert cell_a1["formula_type"] == "shared"
        assert cell_a1["formula_ref"] == "A1:A5"
        assert cell_a1["formula_si"] == 0
        assert cell_a1["cached_value"] == 10
        assert cell_a1["value"] == 10

        # Follower cell A2 (shared formula group member with empty formula tag)
        cell_a2 = rows[1]["cells"][0]
        assert cell_a2["coordinate"] == "A2"
        assert cell_a2["formula"] is None
        assert cell_a2["formula_type"] == "shared"
        assert cell_a2["formula_ref"] is None
        assert cell_a2["formula_si"] == 0
        assert cell_a2["cached_value"] == 20
        assert cell_a2["value"] == 20

    def test_shared_formula_distinct_follower_cached_values(self, tmp_path: Path) -> None:
        """Verify master and follower cells maintain independent cached values without cross-inheritance."""
        shared_f_path = tmp_path / "shared_formula_multi.xlsx"
        create_minimal_xlsx(shared_f_path)

        shared_f_sheet = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1">'
            '<c r="A1"><f t="shared" ref="A1:A3" si="0">B1*10</f><v>100</v></c>'
            '</row>'
            '<row r="2">'
            '<c r="A2"><f t="shared" si="0"/><v>250</v></c>'
            '</row>'
            '<row r="3">'
            '<c r="A3"><f si="0"/><v>999</v></c>'
            '</row>'
            '<row r="4">'
            '<c r="A4"><v>500</v></c>'
            '</row>'
            '</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(shared_f_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="SharedF" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", shared_f_sheet)

        reader = StreamingWorkbookReader(shared_f_path)
        chunks = list(reader.stream_sheet(0))
        assert len(chunks) == 1
        rows = chunks[0]
        assert len(rows) == 4

        # 1. Master cell A1
        c_a1 = rows[0]["cells"][0]
        assert c_a1["coordinate"] == "A1"
        assert c_a1["formula"] == "B1*10"
        assert c_a1["formula_type"] == "shared"
        assert c_a1["formula_ref"] == "A1:A3"
        assert c_a1["formula_si"] == 0
        assert c_a1["value"] == 100
        assert c_a1["cached_value"] == 100

        # 2. Follower cell A2 (explicit t="shared")
        c_a2 = rows[1]["cells"][0]
        assert c_a2["coordinate"] == "A2"
        assert c_a2["formula"] is None
        assert c_a2["formula_type"] == "shared"
        assert c_a2["formula_ref"] is None
        assert c_a2["formula_si"] == 0
        assert c_a2["value"] == 250
        assert c_a2["cached_value"] == 250
        assert c_a2["cached_value"] != c_a1["cached_value"]  # No incorrect inheritance

        # 3. Follower cell A3 (implicit shared formula via si="0" without t attribute)
        c_a3 = rows[2]["cells"][0]
        assert c_a3["coordinate"] == "A3"
        assert c_a3["formula"] is None
        assert c_a3["formula_type"] == "shared"
        assert c_a3["formula_ref"] is None
        assert c_a3["formula_si"] == 0
        assert c_a3["value"] == 999
        assert c_a3["cached_value"] == 999
        assert c_a3["cached_value"] != c_a1["cached_value"]
        assert c_a3["cached_value"] != c_a2["cached_value"]

        # 4. Standard non-formula cell A4
        c_a4 = rows[3]["cells"][0]
        assert c_a4["coordinate"] == "A4"
        assert c_a4["formula"] is None
        assert c_a4["formula_type"] is None
        assert c_a4["formula_si"] is None
        assert c_a4["value"] == 500
        assert c_a4["cached_value"] is None

    def test_canonical_and_compatibility_parser_imports(self) -> None:
        """Verify that canonical excel_intel.core.parser and compatibility excel_intel.parser match."""
        import excel_intel.core.parser as core_parser
        import excel_intel.parser as compat_parser

        assert core_parser.StreamingWorkbookReader is compat_parser.StreamingWorkbookReader
        assert core_parser.PlatformResourceLimitError is compat_parser.PlatformResourceLimitError
        assert core_parser.CorruptWorkbookError is compat_parser.CorruptWorkbookError
        assert core_parser.UnsupportedFormatError is compat_parser.UnsupportedFormatError
        assert core_parser.DateOutOfRangeError is compat_parser.DateOutOfRangeError
