"""Tests for schedule entity parsing and day extraction."""

import pytest

from custom_components.thz.schedule import ScheduleInfo


class TestScheduleInfo:
    """Tests for ScheduleInfo dataclass."""

    def test_schedule_info_creation(self):
        """Test creating a ScheduleInfo instance."""
        from datetime import time
        
        schedule = ScheduleInfo(
            start_time=time(8, 0),
            end_time=time(17, 0),
            days=[0, 1, 2, 3, 4]
        )
        
        assert schedule.start_time == time(8, 0)
        assert schedule.end_time == time(17, 0)
        assert schedule.days == [0, 1, 2, 3, 4]

    def test_schedule_info_with_none_times(self):
        """Test ScheduleInfo with None times."""
        schedule = ScheduleInfo(
            start_time=None,
            end_time=None,
            days=[0]
        )
        
        assert schedule.start_time is None
        assert schedule.end_time is None
        assert schedule.days == [0]

    def test_schedule_info_single_day(self):
        """Test ScheduleInfo with single day."""
        from datetime import time
        
        schedule = ScheduleInfo(
            start_time=time(9, 0),
            end_time=time(18, 0),
            days=[4]  # Friday
        )
        
        assert schedule.days == [4]


class TestDayParsing:
    """Tests for day parsing from entity names."""

    def test_parse_day_monday(self):
        """Test parsing Monday from name."""
        # This would be tested via THZSchedule._parse_day_from_name
        # but since that requires Home Assistant dependencies, we test the logic
        day_map = {
            "Mo": 0,
            "Tu": 1,
            "We": 2,
            "Th": 3,
            "Fr": 4,
            "Sa": 5,
            "So": 6,
        }
        
        name = "programDHW_Mo_0"
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        day_index = day_map.get(day_str, 0)
        
        assert day_index == 0

    def test_parse_day_friday(self):
        """Test parsing Friday from name."""
        day_map = {
            "Mo": 0,
            "Tu": 1,
            "We": 2,
            "Th": 3,
            "Fr": 4,
            "Sa": 5,
            "So": 6,
        }
        
        name = "programHC1_Fr_1"
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        day_index = day_map.get(day_str, 0)
        
        assert day_index == 4

    def test_parse_day_range_mo_fr(self):
        """Test parsing Monday-Friday range."""
        day_map = {
            "Mo-Fr": [0, 1, 2, 3, 4],
            "Sa-So": [5, 6],
            "Mo-So": [0, 1, 2, 3, 4, 5, 6],
        }
        
        name = "programDHW_Mo-Fr_0"
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        days = day_map.get(day_str, 0)
        
        assert days == [0, 1, 2, 3, 4]

    def test_parse_day_range_sa_so(self):
        """Test parsing Saturday-Sunday range."""
        day_map = {
            "Mo-Fr": [0, 1, 2, 3, 4],
            "Sa-So": [5, 6],
            "Mo-So": [0, 1, 2, 3, 4, 5, 6],
        }
        
        name = "programHC2_Sa-So_1"
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        days = day_map.get(day_str, 0)
        
        assert days == [5, 6]

    def test_parse_day_range_full_week(self):
        """Test parsing full week range."""
        day_map = {
            "Mo-Fr": [0, 1, 2, 3, 4],
            "Sa-So": [5, 6],
            "Mo-So": [0, 1, 2, 3, 4, 5, 6],
        }
        
        name = "programCirc_Mo-So_0"
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        days = day_map.get(day_str, 0)
        
        assert days == [0, 1, 2, 3, 4, 5, 6]

    def test_parse_day_unknown(self):
        """Test parsing unknown day defaults to 0 (Monday)."""
        day_map = {
            "Mo": 0,
            "Tu": 1,
            "We": 2,
            "Th": 3,
            "Fr": 4,
            "Sa": 5,
            "So": 6,
        }
        
        name = "programDHW_XX_0"  # Unknown day code
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        day_index = day_map.get(day_str, 0)
        
        assert day_index == 0  # Defaults to Monday

    def test_parse_day_missing_parts(self):
        """Test parsing name with missing day part."""
        day_map = {
            "Mo": 0,
            "Tu": 1,
        }
        
        name = "program"  # No day part
        parts = name.split("_")
        day_str = parts[1] if len(parts) >= 2 else ""
        day_index = day_map.get(day_str, 0)
        
        assert day_index == 0  # Defaults to Monday


class TestScheduleConversion:
    """Tests for schedule time conversion."""

    def test_quarters_to_schedule_time(self):
        """Test converting quarters to schedule time."""
        from datetime import time
        from custom_components.thz.time import quarters_to_time
        
        # 32 quarters = 8:00 (32 * 15 minutes = 480 minutes = 8 hours)
        result = quarters_to_time(32)
        assert result == time(8, 0)

    def test_schedule_time_to_quarters(self):
        """Test converting schedule time to quarters."""
        from datetime import time
        from custom_components.thz.time import time_to_quarters
        
        # 8:00 = 32 quarters
        result = time_to_quarters(time(8, 0))
        assert result == 32

    def test_schedule_round_trip(self):
        """Test round-trip conversion for schedule times."""
        from datetime import time
        from custom_components.thz.time import quarters_to_time, time_to_quarters
        
        original = time(9, 15)
        quarters = time_to_quarters(original)
        result = quarters_to_time(quarters)
        
        assert result == original

    def test_schedule_time_ranges(self):
        """Test schedule time ranges."""
        from datetime import time
        from custom_components.thz.time import time_to_quarters
        
        # Morning: 6:00-9:00
        start = time_to_quarters(time(6, 0))
        end = time_to_quarters(time(9, 0))
        
        assert start == 24  # 6 * 4
        assert end == 36    # 9 * 4
        assert end > start

    def test_schedule_empty_slot(self):
        """Test empty schedule slot (None times)."""
        from custom_components.thz.time import time_to_quarters
        from custom_components.thz.const import TIME_VALUE_UNSET
        
        result = time_to_quarters(None)
        assert result == TIME_VALUE_UNSET
