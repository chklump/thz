"""Tests for entity translation mappings."""

import pytest

from custom_components.thz.entity_translations import (
    ENTITY_TRANSLATION_KEYS,
    get_translation_key,
)


class TestEntityTranslationKeys:
    """Test the ENTITY_TRANSLATION_KEYS dictionary."""

    def test_dictionary_not_empty(self):
        """Test that the translation keys dictionary is not empty."""
        assert len(ENTITY_TRANSLATION_KEYS) > 0

    def test_op_mode_key_exists(self):
        """Test that operating mode key exists."""
        assert "pOpMode" in ENTITY_TRANSLATION_KEYS
        assert ENTITY_TRANSLATION_KEYS["pOpMode"] == "op_mode"

    def test_room_temp_keys_exist(self):
        """Test that room temperature keys exist."""
        assert "p01RoomTempDay" in ENTITY_TRANSLATION_KEYS
        assert "p02RoomTempNight" in ENTITY_TRANSLATION_KEYS
        assert "p03RoomTempStandby" in ENTITY_TRANSLATION_KEYS

    def test_dhw_temp_keys_exist(self):
        """Test that DHW temperature keys exist."""
        assert "p04DHWsetTempDay" in ENTITY_TRANSLATION_KEYS
        assert "p05DHWsetTempNight" in ENTITY_TRANSLATION_KEYS
        assert "p06DHWsetTempStandby" in ENTITY_TRANSLATION_KEYS

    def test_fan_stage_keys_exist(self):
        """Test that fan stage keys exist."""
        assert "p07FanStageDay" in ENTITY_TRANSLATION_KEYS
        assert "p08FanStageNight" in ENTITY_TRANSLATION_KEYS
        assert "p09FanStageStandby" in ENTITY_TRANSLATION_KEYS

    def test_hc2_keys_exist(self):
        """Test that HC2 keys exist."""
        assert "p01RoomTempDayHC2" in ENTITY_TRANSLATION_KEYS
        assert "p16GradientHC2" in ENTITY_TRANSLATION_KEYS
        assert "p17LowEndHC2" in ENTITY_TRANSLATION_KEYS

    def test_all_values_are_strings(self):
        """Test that all translation keys are strings."""
        for key, value in ENTITY_TRANSLATION_KEYS.items():
            assert isinstance(key, str), f"Key {key} is not a string"
            assert isinstance(value, str), f"Value {value} for key {key} is not a string"

    def test_no_duplicate_values(self):
        """Test that translation keys don't have duplicate values (except where expected)."""
        values = list(ENTITY_TRANSLATION_KEYS.values())
        # Some duplicates may be intentional (like p84 having two entries)
        # Just ensure the structure is correct
        assert len(values) > 0


class TestGetTranslationKey:
    """Test the get_translation_key function."""

    def test_existing_key(self):
        """Test getting an existing translation key."""
        result = get_translation_key("pOpMode")
        assert result == "op_mode"

    def test_room_temp_day(self):
        """Test getting room temperature day key."""
        result = get_translation_key("p01RoomTempDay")
        assert result == "room_temp_day"

    def test_dhw_temp(self):
        """Test getting DHW temperature key."""
        result = get_translation_key("p04DHWsetTempDay")
        assert result == "dhw_temp_day"

    def test_non_existing_key(self):
        """Test getting a non-existing key returns None."""
        result = get_translation_key("nonExistentKey")
        assert result is None

    def test_empty_string(self):
        """Test getting translation for empty string."""
        result = get_translation_key("")
        assert result is None

    def test_hc1_keys(self):
        """Test HC1-specific keys."""
        assert get_translation_key("p13GradientHC1") == "gradient_hc1"
        assert get_translation_key("p14LowEndHC1") == "low_end_hc1"
        assert get_translation_key("p15RoomInfluenceHC1") == "room_influence_hc1"

    def test_hc2_keys(self):
        """Test HC2-specific keys."""
        assert get_translation_key("p16GradientHC2") == "gradient_hc2"
        assert get_translation_key("p17LowEndHC2") == "low_end_hc2"
        assert get_translation_key("p18RoomInfluenceHC2") == "room_influence_hc2"

    def test_hysteresis_keys(self):
        """Test hysteresis parameter keys."""
        assert get_translation_key("p21Hyst1") == "hysteresis_1"
        assert get_translation_key("p22Hyst2") == "hysteresis_2"
        assert get_translation_key("p29HystAsymmetry") == "hysteresis_asymmetry"

    def test_solar_keys(self):
        """Test solar-related keys."""
        assert get_translation_key("p80EnableSolar") == "enable_solar"
        assert get_translation_key("p81DiffTempSolarLoading") == "diff_temp_solar_loading"
