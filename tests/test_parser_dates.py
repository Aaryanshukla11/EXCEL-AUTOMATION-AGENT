"""Tests for Excel date and datetime serial conversions (M02).

Validates IEEE-754 boundary safety, piecewise 1900 date system (including Lotus serial 60),
independent 1904 date system, subsecond millisecond rounding, and day-carry rollover.
"""

import datetime
import math
import struct
import pytest

from excel_intel.core.parser import (
    DateOutOfRangeError,
    ParserError,
    parse_excel_serial,
)


def to_bits(val: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", val))[0]


def from_bits(bits: int) -> float:
    return struct.unpack(">d", struct.pack(">Q", bits))[0]


MS_PER_DAY = 86_400_000.0
HALF_MS_DAY_FRAC = 0.5 / MS_PER_DAY
UPPER_BOUND_1900 = 2_958_466.0 - HALF_MS_DAY_FRAC
UPPER_BOUND_1904 = 2_957_004.0 - HALF_MS_DAY_FRAC


class TestDateSystem1900:
    """Test suite for Excel 1900 date system."""

    def test_serial_zero_and_time_only(self) -> None:
        # Serial 0.0 -> unanchored serial zero
        assert parse_excel_serial(0.0, is_1904=False) == "EXCEL_SERIAL_ZERO"

        # Fractional serial 0.5 -> 12:00:00 time-only
        res_noon = parse_excel_serial(0.5, is_1904=False)
        assert isinstance(res_noon, datetime.time)
        assert res_noon == datetime.time(12, 0, 0)

        # Fractional serial 0.75 -> 18:00:00 time-only
        res_evening = parse_excel_serial(0.75, is_1904=False)
        assert isinstance(res_evening, datetime.time)
        assert res_evening == datetime.time(18, 0, 0)

    def test_serial_1_and_fractional(self) -> None:
        # Serial 1.0 -> 1900-01-01 date-only
        res_1 = parse_excel_serial(1.0, is_1904=False)
        assert isinstance(res_1, datetime.date)
        assert res_1 == datetime.date(1900, 1, 1)

        # Serial 1.5 -> 1900-01-01 12:00:00
        res_1_5 = parse_excel_serial(1.5, is_1904=False)
        assert isinstance(res_1_5, datetime.datetime)
        assert res_1_5 == datetime.datetime(1900, 1, 1, 12, 0, 0)

    def test_serial_59_feb_28(self) -> None:
        res_59 = parse_excel_serial(59.0, is_1904=False)
        assert res_59 == datetime.date(1900, 2, 28)

    def test_serial_60_fictitious_leap_day(self) -> None:
        # Serial 60.0 -> Lotus 1-2-3 defect tagged representation
        res_60 = parse_excel_serial(60.0, is_1904=False)
        assert isinstance(res_60, dict)
        assert res_60["__excel_special_date__"] == "1900-02-29"
        assert "time" not in res_60

        # Serial 60.5 -> Lotus defect with fractional time
        res_60_noon = parse_excel_serial(60.5, is_1904=False)
        assert isinstance(res_60_noon, dict)
        assert res_60_noon["__excel_special_date__"] == "1900-02-29"
        assert res_60_noon["time"] == "12:00:00"

    def test_serial_61_march_1(self) -> None:
        res_61 = parse_excel_serial(61.0, is_1904=False)
        assert res_61 == datetime.date(1900, 3, 1)

    def test_day_carry_transition_to_serial_60(self) -> None:
        # 59.999999999 carries into serial 60
        s_carry = 59.0 + (86_399_999.6 / 86_400_000.0)
        res = parse_excel_serial(s_carry, is_1904=False)
        assert isinstance(res, dict)
        assert res["__excel_special_date__"] == "1900-02-29"

    def test_day_carry_transition_to_serial_61(self) -> None:
        # 60.999999999 carries into serial 61 (1900-03-01)
        s_carry = 60.0 + (86_399_999.6 / 86_400_000.0)
        res = parse_excel_serial(s_carry, is_1904=False)
        assert isinstance(res, datetime.datetime)
        assert res == datetime.datetime(1900, 3, 1, 0, 0, 0)


class TestDateSystem1904:
    """Test suite for Excel 1904 date system."""

    def test_serial_0_and_fractions(self) -> None:
        # Serial 0.0 -> 1904-01-01
        res_0 = parse_excel_serial(0.0, is_1904=True)
        assert isinstance(res_0, datetime.date)
        assert res_0 == datetime.date(1904, 1, 1)

        # Serial 0.5 -> 1904-01-01 12:00:00
        res_0_5 = parse_excel_serial(0.5, is_1904=True)
        assert isinstance(res_0_5, datetime.datetime)
        assert res_0_5 == datetime.datetime(1904, 1, 1, 12, 0, 0)

    def test_serial_1_and_fractions(self) -> None:
        # Serial 1.0 -> 1904-01-02
        res_1 = parse_excel_serial(1.0, is_1904=True)
        assert isinstance(res_1, datetime.date)
        assert res_1 == datetime.date(1904, 1, 2)

        # Serial 1.5 -> 1904-01-02 12:00:00
        res_1_5 = parse_excel_serial(1.5, is_1904=True)
        assert isinstance(res_1_5, datetime.datetime)
        assert res_1_5 == datetime.datetime(1904, 1, 2, 12, 0, 0)

    def test_1904_previous_millisecond(self) -> None:
        max_day = 2_957_003.0
        # 23:59:59.998
        s_prev = max_day + (86_399_998.0 / 86_400_000.0)
        res_prev = parse_excel_serial(s_prev, is_1904=True)
        assert res_prev == datetime.datetime(9999, 12, 31, 23, 59, 59, 998000)

        # 23:59:59.999
        s_exact = max_day + (86_399_999.0 / 86_400_000.0)
        res_exact = parse_excel_serial(s_exact, is_1904=True)
        assert res_exact == datetime.datetime(9999, 12, 31, 23, 59, 59, 999000)


class TestIEEE754AdjacentBoundaries:
    """Test suite verifying adjacent IEEE-754 bit representations around upper bounds."""

    def test_1900_adjacent_bits(self) -> None:
        bits = to_bits(UPPER_BOUND_1900)

        # previous = bits - 1 -> MUST BE ACCEPTED (9999-12-31 23:59:59.999)
        prev_f = from_bits(bits - 1)
        res_prev = parse_excel_serial(prev_f, is_1904=False)
        assert res_prev == datetime.datetime(9999, 12, 31, 23, 59, 59, 999000)

        # upper_bound -> MUST BE REJECTED
        with pytest.raises(DateOutOfRangeError):
            parse_excel_serial(UPPER_BOUND_1900, is_1904=False)

        # next = bits + 1 -> MUST BE REJECTED
        next_f = from_bits(bits + 1)
        with pytest.raises(DateOutOfRangeError):
            parse_excel_serial(next_f, is_1904=False)

    def test_1904_adjacent_bits(self) -> None:
        bits = to_bits(UPPER_BOUND_1904)

        # previous = bits - 1 -> MUST BE ACCEPTED (9999-12-31 23:59:59.999)
        prev_f = from_bits(bits - 1)
        res_prev = parse_excel_serial(prev_f, is_1904=True)
        assert res_prev == datetime.datetime(9999, 12, 31, 23, 59, 59, 999000)

        # upper_bound -> MUST BE REJECTED
        with pytest.raises(DateOutOfRangeError):
            parse_excel_serial(UPPER_BOUND_1904, is_1904=True)

        # next = bits + 1 -> MUST BE REJECTED
        next_f = from_bits(bits + 1)
        with pytest.raises(DateOutOfRangeError):
            parse_excel_serial(next_f, is_1904=True)


class TestExtremeNumericSafety:
    """Verifies that extreme floats cannot cause float-to-int saturation or panics."""

    @pytest.mark.parametrize("val", [1e300, 1e20, float("inf"), float("-inf"), float("nan"), -0.1, -100.0, 3e6])
    def test_invalid_and_out_of_range_values(self, val: float) -> None:
        for is_1904 in [False, True]:
            with pytest.raises(ParserError):
                parse_excel_serial(val, is_1904=is_1904)
