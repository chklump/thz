# Tests for THZ Integration

This directory contains unit tests for the THZ Home Assistant custom integration.

## Running Tests

### Prerequisites

```bash
pip install -r requirements_test.txt
```

### Run All Tests

```bash
python3 -m pytest tests/ -v
```

### Run Specific Test File

```bash
python3 -m pytest tests/test_time_conversion.py -v
```

### Run with Coverage

```bash
python3 -m pytest tests/ --cov=custom_components/thz --cov-report=html
```

## Test Structure

- `conftest.py` - Test configuration and Home Assistant module mocking
- `test_helpers.py` - Helper functions used by tests
- `test_time_conversion.py` - Tests for time conversion functions (20 tests)
- `test_decode_value.py` - Tests for sensor value decoding (27 tests)
- `test_protocol.py` - Tests for THZ protocol functions (18 tests)

## Test Coverage

### Time Conversion (20 tests)
- `time_to_quarters()` - Convert time to 15-minute quarter values
- `quarters_to_time()` - Convert quarter values back to time
- Round-trip conversions
- Edge cases (midnight, end of day, None values)
- Invalid value handling

### Sensor Decoding (27 tests)
- `hex2int` - Signed integer decoding with factors
- `hex` - Unsigned integer decoding
- `bitX` - Bit extraction
- `nbitX` - Negated bit extraction
- `esp_mant` - Float decoding with mantissa/exponent
- Edge cases and multi-byte handling

### Protocol Functions (18 tests)
- Checksum calculation (`thz_checksum`)
- Data escaping (`escape`/`unescape`)
- Telegram construction
- Cache functionality
- Round-trip encode/decode

## Test Results

All 65 tests pass ✅

```
============================= 65 passed in 1.08s ==============================
```

## Adding New Tests

1. Create a new test file in `tests/` directory
2. Import necessary functions and fixtures
3. Use pytest class-based structure for organization
4. Run tests to verify

Example:
```python
class TestNewFeature:
    """Tests for new feature."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = my_function(input)
        assert result == expected
```

## Continuous Integration

Tests are automatically run on pull requests via GitHub Actions (when configured).
