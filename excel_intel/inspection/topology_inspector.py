"""Sheet Topology Inspector (M03).

Discovers and represents worksheet dimensions, merged cell ranges, hidden rows/columns,
and structural grid properties in a single pass without redundant decompression.
Preserves exact 1-indexed source coordinates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union
import xml.etree.ElementTree as ET

from excel_intel.core.parser import CorruptWorkbookError
from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
    HiddenInterval,
    SheetVisibility,
    StructuralAnomaly,
)
from excel_intel.inspection.package_inspector import PackageStructureInspector

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Resource caps per sheet
MAX_MERGE_CELLS_PER_SHEET = 5000
MAX_HIDDEN_INTERVALS_PER_SHEET = 2000


def consolidate_intervals(
    indices: list[int], dimension: str
) -> list[HiddenInterval]:
    """Consolidate a list of 1-indexed integers into contiguous HiddenIntervals.

    Args:
        indices: List of row or column numbers.
        dimension: 'row' or 'col'.

    Returns:
        Sorted, non-overlapping list of HiddenInterval objects.
    """
    if not indices:
        return []

    sorted_indices = sorted(set(indices))
    intervals: list[HiddenInterval] = []

    start = sorted_indices[0]
    end = start

    for idx in sorted_indices[1:]:
        if idx == end + 1:
            end = idx
        else:
            intervals.append(
                HiddenInterval(dimension=dimension, start=start, end=end)
            )
            start = idx
            end = idx

    intervals.append(HiddenInterval(dimension=dimension, start=start, end=end))
    return intervals


class SheetTopologyInspector:
    """Extracts and models declared OpenXML worksheet topology."""

    def __init__(self, reader: StreamingWorkbookReader) -> None:
        self.reader = reader
        self._package_inspector = PackageStructureInspector(reader)

    def inspect_topology(
        self, sheet: Union[str, int]
    ) -> tuple[DeclaredOpenXmlFacts, list[StructuralAnomaly]]:
        """Extract full topology and declared facts for a given worksheet.

        Args:
            sheet: Sheet name (str) or 0-indexed position (int).

        Returns:
            Tuple of (DeclaredOpenXmlFacts, list of StructuralAnomaly).
        """
        # Resolve sheet name
        if isinstance(sheet, int):
            names = self.reader.sheet_names
            if sheet < 0 or sheet >= len(names):
                raise ValueError(
                    f"Sheet index {sheet} out of range (0..{len(names)-1})"
                )
            sheet_name = names[sheet]
            sheet_index = sheet
        else:
            sheet_name = str(sheet)
            names = self.reader.sheet_names
            if sheet_name not in names:
                raise ValueError(f"Sheet '{sheet_name}' not found in workbook")
            sheet_index = names.index(sheet_name)

        sheet_path = self.reader.get_sheet_path(sheet_name)
        if not sheet_path:
            raise CorruptWorkbookError(
                f"Package path for sheet '{sheet_name}' not found"
            )

        # Retrieve declared sheet properties from catalog
        catalog = self._package_inspector.inspect_sheet_catalog()
        sheet_props: Optional[DeclaredSheetProperties] = None
        for prop in catalog:
            if prop.name == sheet_name:
                sheet_props = prop
                break

        if sheet_props is None:
            sheet_props = DeclaredSheetProperties(
                sheet_id=sheet_index + 1,
                name=sheet_name,
                visibility=SheetVisibility.VISIBLE,
            )

        sheet_xml = self.reader.read_package_part(sheet_path)
        if not sheet_xml:
            raise CorruptWorkbookError(f"Missing sheet XML part: {sheet_path}")

        try:
            root = ET.fromstring(sheet_xml)
        except ET.ParseError as e:
            raise CorruptWorkbookError(
                f"Malformed worksheet XML in '{sheet_path}': {e}"
            ) from e

        anomalies: list[StructuralAnomaly] = []

        # 1. Dimension element: <dimension ref="A1:Z500"/>
        declared_dim_box: Optional[BoundingBox] = None
        declared_dim_ref: Optional[str] = None
        dim_elem = root.find(f"{{{_NS_MAIN}}}dimension")
        if dim_elem is None:
            dim_elem = root.find("dimension")

        if dim_elem is not None:
            declared_dim_ref = dim_elem.attrib.get("ref")
            if declared_dim_ref:
                try:
                    declared_dim_box = BoundingBox.from_a1_ref(declared_dim_ref)
                except ValueError as e:
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_dim_{sheet_name}",
                            severity=AnomalySeverity.WARNING,
                            code="ANOM_INVALID_DIMENSION_REF",
                            message=f"Invalid dimension reference '{declared_dim_ref}': {e}",
                        )
                    )

        # Update properties with dimension facts
        sheet_props = DeclaredSheetProperties(
            sheet_id=sheet_props.sheet_id,
            name=sheet_props.name,
            visibility=sheet_props.visibility,
            declared_dimension_ref=declared_dim_ref,
            declared_dimension_box=declared_dim_box,
            tab_color_rgb=sheet_props.tab_color_rgb,
        )

        # 2. Hidden Columns from <cols><col min="X" max="Y" hidden="1"/></cols>
        hidden_cols_raw: list[int] = []
        cols_elem = root.find(f"{{{_NS_MAIN}}}cols")
        if cols_elem is None:
            cols_elem = root.find("cols")
        if cols_elem is not None:
            for col_elem in cols_elem:
                is_hidden = col_elem.attrib.get("hidden", "").lower() in (
                    "true",
                    "1",
                )
                if is_hidden:
                    try:
                        c_min = int(col_elem.attrib.get("min", "0"))
                        c_max = int(col_elem.attrib.get("max", "0"))
                        if 1 <= c_min <= c_max <= 16384:
                            hidden_cols_raw.extend(range(c_min, c_max + 1))
                    except ValueError:
                        pass

        hidden_columns = consolidate_intervals(hidden_cols_raw, dimension="col")

        # 3. Hidden Rows from <sheetData><row r="X" hidden="1"/></sheetData>
        hidden_rows_raw: list[int] = []
        sheet_data = root.find(f"{{{_NS_MAIN}}}sheetData")
        if sheet_data is None:
            sheet_data = root.find("sheetData")
        if sheet_data is not None:
            for row_elem in sheet_data:
                is_hidden = row_elem.attrib.get("hidden", "").lower() in (
                    "true",
                    "1",
                )
                if is_hidden:
                    try:
                        r_idx = int(row_elem.attrib.get("r", "0"))
                        if 1 <= r_idx <= 1048576:
                            hidden_rows_raw.append(r_idx)
                    except ValueError:
                        pass

        hidden_rows = consolidate_intervals(hidden_rows_raw, dimension="row")

        # 4. Merged Cells from <mergeCells><mergeCell ref="A1:B2"/></mergeCells>
        merge_cells: list[DeclaredMergeCell] = []
        merge_cells_elem = root.find(f"{{{_NS_MAIN}}}mergeCells")
        if merge_cells_elem is None:
            merge_cells_elem = root.find("mergeCells")
        if merge_cells_elem is not None:
            seen_boxes: list[BoundingBox] = []
            for m_elem in merge_cells_elem:
                if len(merge_cells) >= MAX_MERGE_CELLS_PER_SHEET:
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_merge_cap_{sheet_name}",
                            severity=AnomalySeverity.WARNING,
                            code="ANOM_MERGE_CELL_LIMIT_REACHED",
                            message=f"Merged cells capped at {MAX_MERGE_CELLS_PER_SHEET}",
                        )
                    )
                    break

                m_ref = m_elem.attrib.get("ref", "")
                if not m_ref:
                    continue

                try:
                    m_cell = DeclaredMergeCell.from_ref(m_ref)
                except ValueError as e:
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_invalid_merge_{m_ref}",
                            severity=AnomalySeverity.WARNING,
                            code="ANOM_INVALID_MERGE_REF",
                            message=f"Invalid mergeCell ref '{m_ref}': {e}",
                        )
                    )
                    continue

                # Overlap check against previously seen merge ranges
                for prev_box in seen_boxes:
                    if m_cell.box.intersects(prev_box):
                        anomalies.append(
                            StructuralAnomaly(
                                anomaly_id=f"anom_overlapping_merge_{m_ref}",
                                severity=AnomalySeverity.WARNING,
                                code="ANOM_OVERLAPPING_MERGE_CELLS",
                                message=f"Merge range '{m_ref}' overlaps with '{prev_box.to_a1_ref()}'",
                                box=m_cell.box,
                            )
                        )
                        break

                seen_boxes.append(m_cell.box)
                merge_cells.append(m_cell)

        # 5. Tables associated with this sheet
        tables, table_anomalies = self._package_inspector.inspect_tables_for_sheet(
            sheet_path
        )
        anomalies.extend(table_anomalies)

        facts = DeclaredOpenXmlFacts(
            properties=sheet_props,
            declared_dimension=declared_dim_box,
            merge_cells=merge_cells,
            list_objects=tables,
            hidden_rows=hidden_rows,
            hidden_columns=hidden_columns,
        )

        return facts, anomalies
