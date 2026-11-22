"""Sheet Topology Inspector (M03).

Discovers and represents worksheet dimensions, merged cell ranges, hidden rows/columns,
and structural grid properties in a single pass without redundant decompression.
Preserves exact 1-indexed source coordinates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union
import io
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

        anomalies: list[StructuralAnomaly] = []
        declared_dim_box: Optional[BoundingBox] = None
        declared_dim_ref: Optional[str] = None
        hidden_cols_raw: list[int] = []
        hidden_rows_raw: list[int] = []
        merge_cells: list[DeclaredMergeCell] = []
        seen_boxes: list[BoundingBox] = []

        try:
            f = io.StringIO(sheet_xml)
            del sheet_xml  # Immediately release full XML string reference
            context = ET.iterparse(f, events=("start", "end"))
            root: Optional[ET.Element] = None

            for event, elem in context:
                tag = elem.tag.split("}")[-1]
                if event == "start" and root is None:
                    root = elem
                elif event == "end":
                    if tag == "dimension":
                        declared_dim_ref = elem.attrib.get("ref")
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
                        elem.clear()
                        if root is not None:
                            root.clear()
                    elif tag == "col":
                        is_hidden = elem.attrib.get("hidden", "").lower() in ("true", "1")
                        if is_hidden:
                            try:
                                c_min = int(elem.attrib.get("min", "0"))
                                c_max = int(elem.attrib.get("max", "0"))
                                if 1 <= c_min <= c_max <= 16384:
                                    hidden_cols_raw.extend(range(c_min, c_max + 1))
                            except ValueError:
                                pass
                        elem.clear()
                    elif tag == "row":
                        is_hidden = elem.attrib.get("hidden", "").lower() in ("true", "1")
                        if is_hidden:
                            try:
                                r_idx = int(elem.attrib.get("r", "0"))
                                if 1 <= r_idx <= 1048576:
                                    hidden_rows_raw.append(r_idx)
                            except ValueError:
                                pass
                        elem.clear()
                        if root is not None:
                            root.clear()
                    elif tag == "c":
                        elem.clear()
                    elif tag == "mergeCell":
                        if len(merge_cells) < MAX_MERGE_CELLS_PER_SHEET:
                            m_ref = elem.attrib.get("ref", "")
                            if m_ref:
                                try:
                                    m_cell = DeclaredMergeCell.from_ref(m_ref)
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
                                except ValueError as e:
                                    anomalies.append(
                                        StructuralAnomaly(
                                            anomaly_id=f"anom_invalid_merge_{m_ref}",
                                            severity=AnomalySeverity.WARNING,
                                            code="ANOM_INVALID_MERGE_REF",
                                            message=f"Invalid mergeCell ref '{m_ref}': {e}",
                                        )
                                    )
                        elif len(merge_cells) == MAX_MERGE_CELLS_PER_SHEET:
                            anomalies.append(
                                StructuralAnomaly(
                                    anomaly_id=f"anom_merge_cap_{sheet_name}",
                                    severity=AnomalySeverity.WARNING,
                                    code="ANOM_MERGE_CELL_LIMIT_REACHED",
                                    message=f"Merged cells capped at {MAX_MERGE_CELLS_PER_SHEET}",
                                )
                            )
                        elem.clear()
                    elif tag in ("cols", "mergeCells", "sheetData", "worksheet"):
                        elem.clear()
                        if root is not None:
                            root.clear()
        except ET.ParseError as e:
            raise CorruptWorkbookError(
                f"Malformed worksheet XML in '{sheet_path}': {e}"
            ) from e

        # Update properties with dimension facts
        sheet_props = DeclaredSheetProperties(
            sheet_id=sheet_props.sheet_id,
            name=sheet_props.name,
            visibility=sheet_props.visibility,
            declared_dimension_ref=declared_dim_ref,
            declared_dimension_box=declared_dim_box,
            tab_color_rgb=sheet_props.tab_color_rgb,
        )

        hidden_columns = consolidate_intervals(hidden_cols_raw, dimension="col")
        hidden_rows = consolidate_intervals(hidden_rows_raw, dimension="row")

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
