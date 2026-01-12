"""Tests for sensor decode_value function."""
import struct

import pytest

from tests.test_helpers import decode_value


class TestDecodeHex2Int:
    """Tests for hex2int decoding."""

    def test_positive_value(self):
        """Test decoding positive integer."""
        raw = b'\x00\x64'  # 100 in hex
        assert decode_value(raw, "hex2int", 10) == 10.0

    def test_negative_value(self):
        """Test decoding negative integer (signed)."""
        raw = b'\xff\x9c'  # -100 in signed 16-bit
        assert decode_value(raw, "hex2int", 10) == -10.0

    def test_zero(self):
        """Test decoding zero."""
        raw = b'\x00\x00'
        assert decode_value(raw, "hex2int", 10) == 0.0

    def test_with_factor_one(self):
        """Test decoding with factor 1."""
        raw = b'\x00\x0a'  # 10 in hex
        assert decode_value(raw, "hex2int", 1) == 10.0

    def test_large_factor(self):
        """Test decoding with large factor."""
        raw = b'\x03\xe8'  # 1000 in hex
        assert decode_value(raw, "hex2int", 100) == 10.0


class TestDecodeHex:
    """Tests for hex decoding (unsigned)."""

    def test_positive_value(self):
        """Test decoding unsigned integer."""
        raw = b'\x00\x64'  # 100
        assert decode_value(raw, "hex") == 100

    def test_large_value(self):
        """Test decoding large unsigned integer."""
        raw = b'\xff\xff'  # 65535
        assert decode_value(raw, "hex") == 65535

    def test_zero(self):
        """Test decoding zero."""
        raw = b'\x00\x00'
        assert decode_value(raw, "hex") == 0


class TestDecodeBit:
    """Tests for bit extraction."""

    def test_bit0_set(self):
        """Test extracting bit 0 when set."""
        raw = b'\x01'  # 0b00000001
        assert decode_value(raw, "bit0") == True

    def test_bit0_clear(self):
        """Test extracting bit 0 when clear."""
        raw = b'\x00'  # 0b00000000
        assert decode_value(raw, "bit0") == False

    def test_bit3_set(self):
        """Test extracting bit 3 when set."""
        raw = b'\x08'  # 0b00001000
        assert decode_value(raw, "bit3") == True

    def test_bit3_clear(self):
        """Test extracting bit 3 when clear."""
        raw = b'\x07'  # 0b00000111
        assert decode_value(raw, "bit3") == False

    def test_bit7_set(self):
        """Test extracting bit 7 (highest bit)."""
        raw = b'\x80'  # 0b10000000
        assert decode_value(raw, "bit7") == True

    def test_multiple_bits_set(self):
        """Test extracting specific bit when multiple are set."""
        raw = b'\xff'  # 0b11111111
        assert decode_value(raw, "bit0") == True
        assert decode_value(raw, "bit4") == True
        assert decode_value(raw, "bit7") == True


class TestDecodeNbit:
    """Tests for negated bit extraction."""

    def test_nbit0_set(self):
        """Test negated bit 0 when original is set."""
        raw = b'\x01'  # 0b00000001
        assert decode_value(raw, "nbit0") == False

    def test_nbit0_clear(self):
        """Test negated bit 0 when original is clear."""
        raw = b'\x00'  # 0b00000000
        assert decode_value(raw, "nbit0") == True

    def test_nbit3_set(self):
        """Test negated bit 3 when original is set."""
        raw = b'\x08'  # 0b00001000
        assert decode_value(raw, "nbit3") == False

    def test_nbit3_clear(self):
        """Test negated bit 3 when original is clear."""
        raw = b'\x07'  # 0b00000111
        assert decode_value(raw, "nbit3") == True


class TestDecodeEspMant:
    """Tests for esp_mant decoding (float)."""

    def test_positive_float(self):
        """Test decoding positive float."""
        # Pack a float value and test decoding
        value = 23.5
        raw = struct.pack('>f', value)
        result = decode_value(raw, "esp_mant")
        assert abs(result - value) < 0.001

    def test_negative_float(self):
        """Test decoding negative float."""
        value = -15.25
        raw = struct.pack('>f', value)
        result = decode_value(raw, "esp_mant")
        assert abs(result - value) < 0.001

    def test_zero_float(self):
        """Test decoding zero."""
        raw = struct.pack('>f', 0.0)
        result = decode_value(raw, "esp_mant")
        assert result == 0.0

    def test_rounding(self):
        """Test that result is rounded to 3 decimal places."""
        value = 1.23456789
        raw = struct.pack('>f', value)
        result = decode_value(raw, "esp_mant")
        # Should be rounded to 3 decimals
        assert len(str(result).split('.')[-1]) <= 3


class TestDecodeDefault:
    """Tests for default hex string return."""

    def test_unknown_decode_type(self):
        """Test that unknown decode type returns hex string."""
        raw = b'\xab\xcd'
        result = decode_value(raw, "unknown_type")
        assert result == "abcd"

    def test_empty_decode_type(self):
        """Test empty decode type returns hex string."""
        raw = b'\x01\x02\x03'
        result = decode_value(raw, "")
        assert result == "010203"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_byte_hex2int(self):
        """Test hex2int with single byte."""
        raw = b'\x0a'
        assert decode_value(raw, "hex2int", 1) == 10.0

    def test_three_byte_hex(self):
        """Test hex with three bytes."""
        raw = b'\x01\x02\x03'
        assert decode_value(raw, "hex") == 66051  # 0x010203

    def test_bit_with_multi_byte(self):
        """Test bit extraction only uses first byte."""
        raw = b'\x01\xff'
        assert decode_value(raw, "bit0") == True
        assert decode_value(raw, "bit1") == False
