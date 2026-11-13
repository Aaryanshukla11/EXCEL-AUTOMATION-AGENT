"""Tests for cell string length validation (M02).

Validates Excel's 32,767 UTF-16 code unit ceiling, 131,072-byte streaming safety limit,
multibyte CJK handling, and supplementary Unicode surrogate pair accounting.
"""

import pytest

from excel_intel.core.parser import (
    PlatformResourceLimitError,
    validate_cell_string,
)


class TestCellStringValidation:
    """Cell string validation tests."""

    def test_ascii_boundary(self) -> None:
        # Exactly 32,767 ASCII characters -> PASS
        s_pass = "a" * 32_767
        validate_cell_string(s_pass)

        # 32,768 ASCII characters -> FAIL
        s_fail = "a" * 32_768
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            validate_cell_string(s_fail)
        assert "32,767" in str(exc_info.value)

    def test_multibyte_bmp_cjk(self) -> None:
        # '\u4E16' is 3 bytes in UTF-8, 1 UTF-16 code unit
        # 32,767 CJK characters = 98,301 UTF-8 bytes -> PASS
        s_cjk = "\u4E16" * 32_767
        assert len(s_cjk.encode("utf-8")) == 98_301
        validate_cell_string(s_cjk)

    def test_supplementary_unicode_surrogate_pairs(self) -> None:
        # '\U0001F600' (😀) is 4 bytes in UTF-8, but 2 UTF-16 code units (surrogate pair)
        # 16,383 emojis = 32,766 UTF-16 units -> PASS
        s_emoji_pass = "\U0001F600" * 16_383
        validate_cell_string(s_emoji_pass)

        # 16,384 emojis = 32,768 UTF-16 units -> FAIL
        s_emoji_fail = "\U0001F600" * 16_384
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            validate_cell_string(s_emoji_fail)
        assert "32,767" in str(exc_info.value)

    def test_buffer_overflow_131kb(self) -> None:
        # Raw payload exceeding 131,072 bytes -> FAIL immediately
        s_overflow = "a" * 131_073
        with pytest.raises(PlatformResourceLimitError) as exc_info:
            validate_cell_string(s_overflow)
        assert "131,072" in str(exc_info.value)
