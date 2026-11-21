"""Secure Package-Level OpenXML Inspector (M03).

Inspects package metadata, defined names, calculation properties, sheet catalog,
and declared Excel tables (ListObjects) strictly through M02 package-access interfaces.
Preserves read-only invariants and decompression guards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
import xml.etree.ElementTree as ET

from excel_intel.core.parser import CorruptWorkbookError
from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    DeclaredDefinedName,
    DeclaredListObject,
    DeclaredSheetProperties,
    SheetVisibility,
    StructuralAnomaly,
)

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader

# OpenXML Namespaces
_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL_TABLE_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/table"
)

# Resource limits
MAX_DEFINED_NAMES = 5000
MAX_TABLES_PER_WORKBOOK = 1000


class PackageStructureInspector:
    """Secure OpenXML package metadata and structure inspector."""

    def __init__(self, reader: StreamingWorkbookReader) -> None:
        self.reader = reader

    def inspect_calc_pr(self) -> dict[str, Any]:
        """Extract workbook calculation properties (<calcPr>).

        Returns:
            Dict of calculation engine properties, or empty dict if not declared.
        """
        workbook_xml = self.reader.read_package_part("xl/workbook.xml")
        if not workbook_xml:
            return {}

        try:
            root = ET.fromstring(workbook_xml)
        except ET.ParseError as e:
            raise CorruptWorkbookError(f"Malformed xl/workbook.xml: {e}") from e

        calc_pr_elem = root.find(f"{{{_NS_MAIN}}}calcPr")
        if calc_pr_elem is None:
            calc_pr_elem = root.find("calcPr")
        if calc_pr_elem is None:
            return {}

        props: dict[str, Any] = {}
        for k, v in calc_pr_elem.attrib.items():
            clean_key = k.split("}")[-1] if "}" in k else k
            # Type normalization
            if v.lower() in ("true", "1"):
                props[clean_key] = True
            elif v.lower() in ("false", "0"):
                props[clean_key] = False
            elif v.isdigit():
                props[clean_key] = int(v)
            else:
                props[clean_key] = v

        return props

    def inspect_sheet_catalog(self) -> list[DeclaredSheetProperties]:
        """Extract declared sheet metadata and visibility from xl/workbook.xml.

        Returns:
            List of DeclaredSheetProperties in declaration order.
        """
        workbook_xml = self.reader.read_package_part("xl/workbook.xml")
        if not workbook_xml:
            raise CorruptWorkbookError("Missing required package part: xl/workbook.xml")

        try:
            root = ET.fromstring(workbook_xml)
        except ET.ParseError as e:
            raise CorruptWorkbookError(f"Malformed xl/workbook.xml: {e}") from e

        sheets_elem = root.find(f"{{{_NS_MAIN}}}sheets")
        if sheets_elem is None:
            sheets_elem = root.find("sheets")
        if sheets_elem is None:
            raise CorruptWorkbookError("No <sheets> element found in xl/workbook.xml")

        catalog: list[DeclaredSheetProperties] = []
        for sheet_elem in sheets_elem:
            tag = sheet_elem.tag.split("}")[-1]
            if tag != "sheet":
                continue

            name = sheet_elem.attrib.get("name", "")
            if not name:
                continue

            try:
                sheet_id = int(sheet_elem.attrib.get("sheetId", "0"))
            except ValueError:
                sheet_id = 0

            state_str = sheet_elem.attrib.get("state", "visible").lower()
            if state_str == "hidden":
                visibility = SheetVisibility.HIDDEN
            elif state_str == "veryhidden":
                visibility = SheetVisibility.VERY_HIDDEN
            else:
                visibility = SheetVisibility.VISIBLE

            catalog.append(
                DeclaredSheetProperties(
                    sheet_id=sheet_id,
                    name=name,
                    visibility=visibility,
                )
            )

        return catalog

    def inspect_defined_names(
        self, sheet_names: list[str]
    ) -> tuple[list[DeclaredDefinedName], list[StructuralAnomaly]]:
        """Extract declared defined names and validate scopes.

        Args:
            sheet_names: List of sheet names for local scope resolution.

        Returns:
            Tuple of (list of DeclaredDefinedName, list of StructuralAnomaly).
        """
        workbook_xml = self.reader.read_package_part("xl/workbook.xml")
        if not workbook_xml:
            return [], []

        try:
            root = ET.fromstring(workbook_xml)
        except ET.ParseError as e:
            raise CorruptWorkbookError(f"Malformed xl/workbook.xml: {e}") from e

        names_elem = root.find(f"{{{_NS_MAIN}}}definedNames")
        if names_elem is None:
            names_elem = root.find("definedNames")
        if names_elem is None:
            return [], []

        defined_names: list[DeclaredDefinedName] = []
        anomalies: list[StructuralAnomaly] = []
        seen_keys: set[tuple[str, str]] = set()

        for idx, elem in enumerate(names_elem):
            if idx >= MAX_DEFINED_NAMES:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_defined_name_cap_{idx}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_DEFINED_NAME_LIMIT_REACHED",
                        message=f"Defined names truncated after reaching maximum limit of {MAX_DEFINED_NAMES}",
                    )
                )
                break

            name = elem.attrib.get("name", "").strip()
            if not name:
                continue

            value = (elem.text or "").strip()
            comment = elem.attrib.get("comment")
            is_hidden = elem.attrib.get("hidden", "").lower() in ("true", "1")

            local_sheet_id: Optional[int] = None
            if "localSheetId" in elem.attrib:
                try:
                    local_sheet_id = int(elem.attrib["localSheetId"])
                except ValueError:
                    local_sheet_id = None

            if local_sheet_id is not None and 0 <= local_sheet_id < len(sheet_names):
                scope = sheet_names[local_sheet_id]
            else:
                scope = "workbook"

            # Check for duplicate name in identical scope
            scope_key = (name.lower(), scope.lower())
            if scope_key in seen_keys:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_dup_name_{name}_{idx}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_DUPLICATE_DEFINED_NAME",
                        message=f"Duplicate defined name '{name}' in scope '{scope}'",
                        evidence=value,
                    )
                )
            seen_keys.add(scope_key)

            defined_names.append(
                DeclaredDefinedName(
                    name=name,
                    value=value,
                    local_sheet_id=local_sheet_id,
                    scope=scope,
                    comment=comment,
                    is_hidden=is_hidden,
                )
            )

        return defined_names, anomalies

    def inspect_tables_for_sheet(
        self, sheet_path: str
    ) -> tuple[list[DeclaredListObject], list[StructuralAnomaly]]:
        """Inspect declared ListObjects (tables) associated with a sheet path.

        Reads sheet relationships (.rels) and associated xl/tables/table*.xml parts.

        Args:
            sheet_path: Internal package path, e.g. 'xl/worksheets/sheet1.xml'.

        Returns:
            Tuple of (list of DeclaredListObject, list of StructuralAnomaly).
        """
        # Determine relationships path
        parts = sheet_path.split("/")
        if len(parts) < 2:
            return [], []
        sheet_filename = parts[-1]
        rels_path = f"xl/worksheets/_rels/{sheet_filename}.rels"

        rels_xml = self.reader.read_package_part(rels_path)
        if not rels_xml:
            return [], []

        try:
            rels_root = ET.fromstring(rels_xml)
        except ET.ParseError:
            return [], []

        table_targets: list[str] = []
        for rel in rels_root:
            rel_type = rel.attrib.get("Type", "")
            if rel_type == _REL_TABLE_TYPE:
                target = rel.attrib.get("Target", "")
                if target:
                    # Resolve relative target
                    if target.startswith("../tables/"):
                        table_targets.append(f"xl/tables/{target[10:]}")
                    elif target.startswith("/xl/tables/"):
                        table_targets.append(target[1:])
                    elif target.startswith("tables/"):
                        table_targets.append(f"xl/{target}")
                    else:
                        table_targets.append(f"xl/{target}")

        tables: list[DeclaredListObject] = []
        anomalies: list[StructuralAnomaly] = []

        for table_path in table_targets:
            if len(tables) >= MAX_TABLES_PER_WORKBOOK:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_table_cap_{table_path}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_TABLE_LIMIT_REACHED",
                        message=f"Table extraction capped at {MAX_TABLES_PER_WORKBOOK} tables",
                    )
                )
                break

            table_xml = self.reader.read_package_part(table_path)
            if not table_xml:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_missing_table_part_{table_path}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_MISSING_TABLE_PART",
                        message=f"Referenced table part '{table_path}' not found in package",
                    )
                )
                continue

            try:
                tbl_root = ET.fromstring(table_xml)
            except ET.ParseError as e:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_corrupt_table_{table_path}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_CORRUPT_TABLE_XML",
                        message=f"Malformed table XML in '{table_path}': {e}",
                    )
                )
                continue

            try:
                tbl_id = int(tbl_root.attrib.get("id", "0"))
            except ValueError:
                tbl_id = 0

            name = tbl_root.attrib.get("name", "")
            display_name = tbl_root.attrib.get("displayName", name)
            ref = tbl_root.attrib.get("ref", "")

            try:
                box = BoundingBox.from_a1_ref(ref)
            except ValueError as e:
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_table_ref_{name}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_INVALID_TABLE_REF",
                        message=f"Table '{name}' has invalid ref '{ref}': {e}",
                    )
                )
                continue

            try:
                header_row_count = int(tbl_root.attrib.get("headerRowCount", "1"))
            except ValueError:
                header_row_count = 1

            try:
                totals_row_count = int(tbl_root.attrib.get("totalsRowCount", "0"))
            except ValueError:
                totals_row_count = 0

            # Table columns
            columns: list[str] = []
            cols_elem = tbl_root.find(f"{{{_NS_MAIN}}}tableColumns")
            if cols_elem is None:
                cols_elem = tbl_root.find("tableColumns")
            if cols_elem is not None:
                for col_elem in cols_elem:
                    col_name = col_elem.attrib.get("name", "")
                    if col_name:
                        columns.append(col_name)

            # AutoFilter
            af_elem = tbl_root.find(f"{{{_NS_MAIN}}}autoFilter")
            if af_elem is None:
                af_elem = tbl_root.find("autoFilter")
            has_auto_filter = af_elem is not None
            auto_filter_ref = af_elem.attrib.get("ref") if af_elem is not None else None

            tables.append(
                DeclaredListObject(
                    id=tbl_id,
                    name=name,
                    display_name=display_name,
                    ref=ref,
                    box=box,
                    header_row_count=header_row_count,
                    totals_row_count=totals_row_count,
                    column_names=columns,
                    has_auto_filter=has_auto_filter,
                    auto_filter_ref=auto_filter_ref,
                )
            )

        return tables, anomalies
