"""Tests for M03 Content Distribution Profiler (content_profiler.py).

Verifies:
1. Single-pass streaming profiling across worksheet rows.
2. Accurate column type distribution and homogeneity ratios.
3. Actual bounding box discovery vs declared dimensions.
4. Layout classification (EMPTY, SINGLE_TABLE, MULTI_TABLE, KEY_VALUE_GRID, SPARSE_MATRIX).
5. Bounded O(C) memory on large row counts (10,000 rows).
6. Source workbook immutability (SHA-256 integrity).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest
from excel_intel.core.parser import (
    StreamingWorkbookReader,
    py_get_process_working_set_bytes,
)
from excel_intel.inspection.content_profiler import ContentDistributionProfiler
from excel_intel.inspection.models import LayoutClassification


def create_profiler_workbook(
    tmp_path: Path,
    filename: str = "profiler_test.xlsx",
    *,
    dimension_ref: str = "A1:C5",
    sheet_data_xml: str = "",
) -> Path:
    """Build minimal OpenXML workbook with specified sheetData XML."""
    wb_path = tmp_path / filename

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension_ref}"/>'
        f"<sheetData>{sheet_data_xml}</sheetData>"
        "</worksheet>"
    )

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
            "</sheets>"
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return wb_path


def test_empty_sheet_profiling(tmp_path: Path) -> None:
    """Verify empty worksheet produces zero counts and EMPTY layout."""
    wb_path = create_profiler_workbook(tmp_path, "empty.xlsx", dimension_ref="A1:A1", sheet_data_xml="")

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1")

        assert profile.sheet_name == "Sheet1"
        assert profile.populated_cell_count == 0
        assert profile.actual_bounding_box is None
        assert profile.layout_classification == LayoutClassification.EMPTY
        assert len(profile.column_profiles) == 0


def test_single_table_layout_profiling(tmp_path: Path) -> None:
    """Verify standard tabular layout is recognized as SINGLE_TABLE."""
    rows = []
    # Row 1: Header (strings)
    rows.append(
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>ID</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Category</t></is></c>'
        "</row>"
    )
    # Rows 2-20: Data rows
    for r in range(2, 21):
        rows.append(
            f'<row r="{r}">'
            f'<c r="A{r}"><v>{r-1}</v></c>'
            f'<c r="B{r}"><v>{(r-1) * 10.5}</v></c>'
            f'<c r="C{r}" t="inlineStr"><is><t>Cat-{r%3}</t></is></c>'
            f"</row>"
        )

    wb_path = create_profiler_workbook(
        tmp_path,
        "single_table.xlsx",
        dimension_ref="A1:C20",
        sheet_data_xml="".join(rows),
    )

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet(0)

        assert profile.sheet_name == "Sheet1"
        assert profile.populated_cell_count == 60  # 20 rows * 3 cols
        assert profile.actual_bounding_box is not None
        assert profile.actual_bounding_box.min_row == 1
        assert profile.actual_bounding_box.max_row == 20
        assert profile.actual_bounding_box.min_col == 1
        assert profile.actual_bounding_box.max_col == 3
        assert profile.layout_classification == LayoutClassification.SINGLE_TABLE

        # Verify column profiles
        col1 = profile.column_profiles[1]
        assert col1.col_index == 1
        assert col1.populated_count == 20
        assert col1.predominant_type == "integer"
        assert col1.homogeneity_ratio == pytest.approx(19 / 20, rel=1e-3)

        col2 = profile.column_profiles[2]
        assert col2.predominant_type == "float"

        col3 = profile.column_profiles[3]
        assert col3.predominant_type == "string"


def test_multi_table_layout_profiling(tmp_path: Path) -> None:
    """Verify two blocks separated by empty rows yield MULTI_TABLE layout."""
    rows = []
    # Block 1: rows 1 to 5 (3 cols)
    for r in range(1, 6):
        rows.append(f'<row r="{r}"><c r="A{r}"><v>{r}</v></c><c r="B{r}"><v>{r*2}</v></c><c r="C{r}"><v>{r*3}</v></c></row>')
    # Gap: rows 6 to 9 empty
    # Block 2: rows 10 to 15 (3 cols)
    for r in range(10, 16):
        rows.append(f'<row r="{r}"><c r="A{r}"><v>{r}</v></c><c r="B{r}"><v>{r*2}</v></c><c r="C{r}"><v>{r*3}</v></c></row>')

    wb_path = create_profiler_workbook(
        tmp_path,
        "multi_table.xlsx",
        dimension_ref="A1:C15",
        sheet_data_xml="".join(rows),
    )

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1")

        assert profile.layout_classification == LayoutClassification.MULTI_TABLE
        blocks = profiler.get_candidate_blocks("Sheet1")
        assert len(blocks) == 2
        assert blocks[0].start_row == 1
        assert blocks[0].end_row == 5
        assert blocks[1].start_row == 10
        assert blocks[1].end_row == 15


def test_key_value_grid_layout_profiling(tmp_path: Path) -> None:
    """Verify 2-column key-value layout classification."""
    rows = []
    for r in range(1, 10):
        rows.append(
            f'<row r="{r}">'
            f'<c r="A{r}" t="inlineStr"><is><t>Key_{r}</t></is></c>'
            f'<c r="B{r}"><v>{r * 100}</v></c>'
            f"</row>"
        )

    wb_path = create_profiler_workbook(
        tmp_path,
        "key_value.xlsx",
        dimension_ref="A1:B9",
        sheet_data_xml="".join(rows),
    )

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1")

        assert profile.layout_classification == LayoutClassification.KEY_VALUE_GRID
        assert profile.actual_bounding_box.min_col == 1
        assert profile.actual_bounding_box.max_col == 2


def test_sparse_matrix_layout_profiling(tmp_path: Path) -> None:
    """Verify widely scattered cells yield SPARSE_MATRIX layout."""
    rows = [
        '<row r="1"><c r="A1"><v>1</v></c></row>',
        '<row r="50"><c r="Z50"><v>2</v></c></row>',
        '<row r="100"><c r="AZ100"><v>3</v></c></row>',
    ]

    wb_path = create_profiler_workbook(
        tmp_path,
        "sparse.xlsx",
        dimension_ref="A1:AZ100",
        sheet_data_xml="".join(rows),
    )

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1")

        assert profile.layout_classification == LayoutClassification.SPARSE_MATRIX
        assert profile.populated_cell_count == 3


def test_understated_dimension_profiling(tmp_path: Path) -> None:
    """Verify actual cells beyond declared dimension are accurately captured."""
    # Declared dimension says A1:B2, but data exists up to D10
    rows = [
        '<row r="1"><c r="A1"><v>1</v></c><c r="B1"><v>2</v></c></row>',
        '<row r="10"><c r="C10"><v>3</v></c><c r="D10"><v>4</v></c></row>',
    ]

    wb_path = create_profiler_workbook(
        tmp_path,
        "understated.xlsx",
        dimension_ref="A1:B2",
        sheet_data_xml="".join(rows),
    )

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1")

        assert profile.actual_bounding_box is not None
        assert profile.actual_bounding_box.min_row == 1
        assert profile.actual_bounding_box.max_row == 10
        assert profile.actual_bounding_box.min_col == 1
        assert profile.actual_bounding_box.max_col == 4
        assert profile.actual_bounding_box.to_a1_ref() == "A1:D10"


def test_large_synthetic_sheet_bounded_memory(tmp_path: Path) -> None:
    """Profile 10,000 synthetic rows and verify bounded memory consumption."""
    rows = []
    for r in range(1, 10001):
        rows.append(
            f'<row r="{r}">'
            f'<c r="A{r}"><v>{r}</v></c>'
            f'<c r="B{r}"><v>{r * 1.5}</v></c>'
            f'<c r="C{r}" t="inlineStr"><is><t>Item {r}</t></is></c>'
            f'<c r="D{r}"><f>A{r}*2</f><v>{r * 2}</v></c>'
            f"</row>"
        )

    wb_path = create_profiler_workbook(
        tmp_path,
        "large_10k.xlsx",
        dimension_ref="A1:D10000",
        sheet_data_xml="".join(rows),
    )

    initial_rss = py_get_process_working_set_bytes()

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        profile = profiler.profile_sheet("Sheet1", chunk_size=2000)

        final_rss = py_get_process_working_set_bytes()
        rss_growth_mb = (final_rss - initial_rss) / (1024 * 1024)

        assert profile.populated_cell_count == 40000
        assert profile.actual_bounding_box.min_row == 1
        assert profile.actual_bounding_box.max_row == 10000
        assert profile.formula_cell_count == 10000
        assert len(profile.column_profiles) == 4

        # Memory growth during single-pass profiling must remain bounded (< 50 MB growth)
        assert rss_growth_mb < 50.0, f"Excessive memory growth during profiling: {rss_growth_mb:.2f} MB"


def test_source_workbook_immutability(tmp_path: Path) -> None:
    """Verify profiling does not modify source workbook file bytes."""
    rows = ['<row r="1"><c r="A1"><v>42</v></c></row>']
    wb_path = create_profiler_workbook(tmp_path, "immutable.xlsx", sheet_data_xml="".join(rows))

    with open(wb_path, "rb") as f:
        sha_before = hashlib.sha256(f.read()).hexdigest()

    with StreamingWorkbookReader(wb_path) as reader:
        profiler = ContentDistributionProfiler(reader)
        _ = profiler.profile_sheet("Sheet1")

    with open(wb_path, "rb") as f:
        sha_after = hashlib.sha256(f.read()).hexdigest()

    assert sha_before == sha_after, "Source workbook was mutated by profiling!"
