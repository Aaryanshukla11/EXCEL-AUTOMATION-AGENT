"""Fine-Grained Pattern Detector for Semantic Data Type Inference (M05).

Provides deterministic value classification across standard Excel data formats:
- Nulls and blanks (whitespace, empty strings, standard tokens)
- Excel error literals (#N/A, #VALUE!, #REF!, #DIV/0!, #NUM!, #NAME?, #NULL!)
- Booleans (TRUE, FALSE, Yes, No, Y, N)
- Currencies ($1,250.50, €500, (£150.00) accounting negatives)
- Percentages (15.5%, -0.25%)
- Dates (ISO-8601, US/European slash dates, month abbreviations, date serials)
- Numbers (integers, comma-separated decimals, scientific notation)
- Strings (general text, SKU codes, descriptions)
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Optional

from excel_intel.core.parser import parse_excel_serial
from excel_intel.types.models import NormalizedValue, ValueCategory

# OpenXML ECMA-376 Part 1 §18.8.30 Predefined Number Formats
_DATE_NUM_FMT_IDS = {
    14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 45, 46, 47,
}
_CURRENCY_NUM_FMT_IDS = {5, 6, 7, 8, 41, 42, 43, 44}
_PERCENT_NUM_FMT_IDS = {9, 10}

# Standard Excel error literals
_ERROR_LITERALS = {
    "#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NUM!", "#NAME?", "#NULL!", "#GETTING_DATA"
}

# Recognized textual null markers (distinguished from pure empty/blank cells)
_TEXT_NULL_MARKERS = {
    "n/a", "na", "-", "--", "---", "null", "none", "nil", "n.a."
}

# Currency regex components
_CURRENCY_SYMBOLS = r"[$€£¥₹]|CHF|kr|R\$|C\$|A\$"
_CURRENCY_PATTERN = re.compile(
    rf"^\s*(?P<neg_paren>\()?\s*(?P<sym>{_CURRENCY_SYMBOLS})?\s*(?P<neg_sign>[-+])?\s*"
    rf"(?P<sym_after>{_CURRENCY_SYMBOLS})?\s*"
    rf"(?P<num>[0-9]{{1,3}}(?:,[0-9]{{3}})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*"
    rf"(?P<close_paren>\))?\s*$"
)

# Percentage regex
_PERCENT_PATTERN = re.compile(
    r"^\s*(?P<neg_paren>\()?\s*(?P<neg_sign>[-+])?\s*"
    r"(?P<num>[0-9]{{1,3}}(?:,[0-9]{{3}})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*%\s*"
    r"(?P<close_paren>\))?\s*$"
)

# Numeric regexes
_INTEGER_PATTERN = re.compile(r"^\s*[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\s*$")
_DECIMAL_PATTERN = re.compile(r"^\s*[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})*\.[0-9]+|[0-9]*\.[0-9]+(?:[eE][+-]?[0-9]+)?|[0-9]+[eE][+-]?[0-9]+)\s*$")

# Date regexes
_ISO_DATE_PATTERN = re.compile(r"^\s*(?P<year>[0-9]{4})[-/](?P<month>[0-9]{1,2})[-/](?P<day>[0-9]{1,2})(?:[T\s][0-9]{1,2}:[0-9]{1,2}(?::[0-9]{1,2})?)?\s*$")
_SLASH_DATE_PATTERN = re.compile(r"^\s*(?P<p1>[0-9]{1,2})[-/.](?P<p2>[0-9]{1,2})[-/.](?P<p3>[0-9]{2,4})\s*$")
_MONTH_NAME_PATTERN = re.compile(
    r"^\s*(?:(?P<d>[0-9]{1,2})[-/\s](?P<m>[A-Za-z]{3,9})[-/\s](?P<y>[0-9]{2,4})|(?P<m2>[A-Za-z]{3,9})\s+(?P<d2>[0-9]{1,2}),?\s+(?P<y2>[0-9]{2,4}))\s*$",
    re.IGNORECASE,
)
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


class PatternDetector:
    """Domain-agnostic pattern detector for cell value categorization."""

    @staticmethod
    def detect_value(
        value: Any,
        formula: Optional[str] = None,
        cell_type: Optional[str] = None,
        style_id: Optional[int] = None,
        format_code: Optional[str] = None,
        *,
        is_1904: bool = False,
        treat_null_markers_as_null: bool = True,
    ) -> NormalizedValue:
        """Categorize a cell value into fine-grained ValueCategory with normalized representation.

        Args:
            value: Raw cell value parsed by M02 reader.
            formula: Optional raw OpenXML formula string (<f> tag).
            cell_type: OpenXML t attribute ("s", "n", "b", "e", "str", "d").
            style_id: OpenXML xf style index if available.
            format_code: Number format code string (e.g. "yyyy-mm-dd", "$#,##0.00").
            is_1904: True if workbook uses 1904 date system.

        Returns:
            NormalizedValue containing category and formatting provenance.
        """
        # 1. Formula Presence
        if formula is not None and str(formula).strip() != "":
            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.FORMULA,
                normalized_value=formula,
            )
        if isinstance(value, str) and value.strip().startswith("="):
            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.FORMULA,
                normalized_value=value.strip(),
            )

        # 2. Excel Error Values
        if cell_type == "e" or (isinstance(value, str) and value.strip().upper() in _ERROR_LITERALS):
            err_code = str(value).strip().upper()
            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.ERROR,
                error_code=err_code,
            )

        # 3. Definite Null / Blank
        if value is None:
            return NormalizedValue(raw_value=None, category=ValueCategory.NULL, normalized_value=None)

        if isinstance(value, str):
            clean_str = value.strip()
            if clean_str == "":
                return NormalizedValue(raw_value=value, category=ValueCategory.NULL, normalized_value=None)

            # Check if text is a recognized textual null marker
            if clean_str.lower() in _TEXT_NULL_MARKERS:
                cat = ValueCategory.NULL if treat_null_markers_as_null else ValueCategory.STRING
                return NormalizedValue(
                    raw_value=value,
                    category=cat,
                    normalized_value=clean_str,
                    is_null_marker=True,
                    null_marker_text=clean_str,
                )

        # 4. Booleans
        if isinstance(value, bool) or cell_type == "b":
            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.BOOLEAN,
                normalized_value=bool(value),
            )

        if isinstance(value, str):
            clean_lower = value.strip().lower()
            if clean_lower in ("true", "false", "yes", "no", "y", "n"):
                b_val = clean_lower in ("true", "yes", "y")
                return NormalizedValue(
                    raw_value=value,
                    category=ValueCategory.BOOLEAN,
                    normalized_value=b_val,
                )

        # 5. Date / Time Objects
        if isinstance(value, (datetime.date, datetime.datetime)):
            d_val = value.date() if isinstance(value, datetime.datetime) else value
            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.DATE,
                normalized_value=d_val,
                parsed_date=d_val,
            )

        # 6. OpenXML Numeric Serials with Style Formatting or format_code
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            is_date_fmt = False
            if style_id is not None and style_id in _DATE_NUM_FMT_IDS:
                is_date_fmt = True
            elif format_code is not None:
                fmt_lower = format_code.lower()
                if any(tok in fmt_lower for tok in ("yy", "mm", "dd", "m/d", "d-m")):
                    is_date_fmt = True

            if is_date_fmt:
                try:
                    parsed = parse_excel_serial(float(value), is_1904=is_1904)
                    if isinstance(parsed, (datetime.date, datetime.datetime)):
                        d_val = parsed.date() if isinstance(parsed, datetime.datetime) else parsed
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.DATE,
                            normalized_value=d_val,
                            parsed_date=d_val,
                            is_date_serial=True,
                            format_code=format_code,
                        )
                except Exception:
                    pass

            if (style_id is not None and style_id in _CURRENCY_NUM_FMT_IDS) or (
                format_code and any(s in format_code for s in ("$", "€", "£", "¥"))
            ):
                return NormalizedValue(
                    raw_value=value,
                    category=ValueCategory.CURRENCY,
                    normalized_value=float(value),
                    currency_symbol=None,
                    format_code=format_code,
                )

            if (style_id is not None and style_id in _PERCENT_NUM_FMT_IDS) or (
                format_code and "%" in format_code
            ):
                val_flt = float(value)
                return NormalizedValue(
                    raw_value=value,
                    category=ValueCategory.PERCENTAGE,
                    normalized_value=val_flt * 100.0,
                    percentage_factor=val_flt,
                    format_code=format_code,
                )

            if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
                int_v = int(value)
                is_bool_cand = int_v in (0, 1)
                return NormalizedValue(
                    raw_value=value,
                    category=ValueCategory.INTEGER,
                    normalized_value=int_v,
                    is_boolean_candidate=is_bool_cand,
                )

            return NormalizedValue(
                raw_value=value,
                category=ValueCategory.DECIMAL,
                normalized_value=float(value),
            )

        # 7. String Pattern Inspection
        if isinstance(value, str):
            clean_str = value.strip()

            # 7.1 Currency Pattern
            c_match = _CURRENCY_PATTERN.match(clean_str)
            if c_match:
                sym = c_match.group("sym") or c_match.group("sym_after")
                is_paren_neg = bool(c_match.group("neg_paren") and c_match.group("close_paren"))
                if sym or is_paren_neg:
                    num_str = c_match.group("num").replace(",", "")
                    is_minus_neg = c_match.group("neg_sign") == "-"
                    is_neg = is_paren_neg or is_minus_neg

                    try:
                        val_float = float(num_str)
                        if is_neg:
                            val_float = -val_float
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.CURRENCY,
                            normalized_value=val_float,
                            currency_symbol=sym,
                            is_accounting_negative=is_paren_neg,
                        )
                    except ValueError:
                        pass

            # 7.2 Percentage Pattern
            p_match = _PERCENT_PATTERN.match(clean_str)
            if p_match:
                num_str = p_match.group("num").replace(",", "")
                is_neg = bool(
                    p_match.group("neg_sign") == "-"
                    or (p_match.group("neg_paren") and p_match.group("close_paren"))
                )
                try:
                    val_float = float(num_str)
                    if is_neg:
                        val_float = -val_float
                    return NormalizedValue(
                        raw_value=value,
                        category=ValueCategory.PERCENTAGE,
                        normalized_value=val_float,
                        percentage_factor=val_float / 100.0,
                    )
                except ValueError:
                    pass

            # 7.3 ISO Date Pattern (YYYY-MM-DD)
            iso_match = _ISO_DATE_PATTERN.match(clean_str)
            if iso_match:
                try:
                    y = int(iso_match.group("year"))
                    m = int(iso_match.group("month"))
                    d = int(iso_match.group("day"))
                    d_obj = datetime.date(y, m, d)
                    return NormalizedValue(
                        raw_value=value,
                        category=ValueCategory.DATE,
                        normalized_value=d_obj,
                        parsed_date=d_obj,
                    )
                except ValueError:
                    pass

            # 7.4 Alphanumeric Date (DD-Mon-YYYY or Mon DD, YYYY)
            m_match = _MONTH_NAME_PATTERN.match(clean_str)
            if m_match:
                try:
                    if m_match.group("m"):
                        m_str = m_match.group("m").lower()
                        d = int(m_match.group("d"))
                        y_raw = int(m_match.group("y"))
                    else:
                        m_str = m_match.group("m2").lower()
                        d = int(m_match.group("d2"))
                        y_raw = int(m_match.group("y2"))

                    m = _MONTH_NAMES.get(m_str)
                    if m:
                        y = y_raw if y_raw >= 100 else (2000 + y_raw if y_raw < 50 else 1900 + y_raw)
                        d_obj = datetime.date(y, m, d)
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.DATE,
                            normalized_value=d_obj,
                            parsed_date=d_obj,
                        )
                except (ValueError, KeyError):
                    pass

            # 7.5 Slash / Dot Date (MM/DD/YYYY, DD/MM/YYYY, or YY/MM/DD)
            s_match = _SLASH_DATE_PATTERN.match(clean_str)
            if s_match:
                p1 = int(s_match.group("p1"))
                p2 = int(s_match.group("p2"))
                p3 = int(s_match.group("p3"))

                # 4-digit or 2-digit year
                if p3 >= 1000:
                    y = p3
                elif p3 < 100:
                    y = 2000 + p3 if p3 < 50 else 1900 + p3
                else:
                    y = p3

                # Check if p1 and p2 could be day/month
                if p1 > 12 and 1 <= p2 <= 12:
                    try:
                        d_obj = datetime.date(y, p2, p1)
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.DATE,
                            normalized_value=d_obj,
                            parsed_date=d_obj,
                        )
                    except ValueError:
                        pass
                elif p2 > 12 and 1 <= p1 <= 12:
                    try:
                        d_obj = datetime.date(y, p1, p2)
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.DATE,
                            normalized_value=d_obj,
                            parsed_date=d_obj,
                        )
                    except ValueError:
                        pass
                elif 1 <= p1 <= 12 and 1 <= p2 <= 12:
                    try:
                        d_obj = datetime.date(y, p1, p2)
                        return NormalizedValue(
                            raw_value=value,
                            category=ValueCategory.DATE,
                            normalized_value=d_obj,
                            parsed_date=d_obj,
                            has_date_order_ambiguity=True,
                        )
                    except ValueError:
                        pass

            # 7.6 Numeric String - Integer
            if _INTEGER_PATTERN.match(clean_str):
                clean_num = clean_str.replace(",", "")
                try:
                    int_val = int(clean_num)
                    is_bool_cand = int_val in (0, 1) and len(clean_num) == 1
                    return NormalizedValue(
                        raw_value=value,
                        category=ValueCategory.INTEGER,
                        normalized_value=int_val,
                        is_boolean_candidate=is_bool_cand,
                    )
                except ValueError:
                    pass

            # 7.7 Numeric String - Decimal
            if _DECIMAL_PATTERN.match(clean_str):
                clean_num = clean_str.replace(",", "")
                try:
                    float_val = float(clean_num)
                    return NormalizedValue(
                        raw_value=value,
                        category=ValueCategory.DECIMAL,
                        normalized_value=float_val,
                    )
                except ValueError:
                    pass

        # 8. Plain Text Fallback
        return NormalizedValue(
            raw_value=value,
            category=ValueCategory.STRING,
            normalized_value=str(value),
        )
