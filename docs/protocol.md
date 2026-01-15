# THZ Protocol Documentation

## Overview

This document describes the communication protocol used by Stiebel Eltron LWZ / Tecalor THZ heat pumps. The protocol is based on serial communication (RS-232) and can be accessed via USB or network (ser2net).

## Connection Methods

### USB/Serial Connection
- **Baud Rate**: 115200 (default)
- **Data Bits**: 8
- **Stop Bits**: 1
- **Parity**: None
- **Flow Control**: None

### Network Connection (ser2net)
- TCP connection to ser2net server
- Default port: 8888
- Same protocol as USB connection

## Protocol Structure

### Request Format

All requests follow this structure:

```
[STX] [CMD] [ADDR_H] [ADDR_L] [DATA...] [CHK] [ETX]
```

- **STX** (0x02): Start of text marker
- **CMD**: Command byte
  - `0x00`: Read request
  - `0x01`: Write request
- **ADDR_H**: High byte of register address
- **ADDR_L**: Low byte of register address
- **DATA**: Optional data bytes for write commands
- **CHK**: Checksum (XOR of all bytes from CMD to last DATA byte)
- **ETX** (0x03): End of text marker

### Response Format

```
[STX] [STATUS] [DATA...] [CHK] [ETX]
```

- **STX** (0x02): Start of text marker
- **STATUS**: Status byte
  - `0x00`: Success
  - `0x01`: Error
- **DATA**: Response data bytes
- **CHK**: Checksum (XOR of all bytes from STATUS to last DATA byte)
- **ETX** (0x03): End of text marker

## Register Map

### Read Registers

Read registers contain sensor data and status information. They are organized into blocks:

- **Block p01 (0xFB0A)**: Operating parameters and temperatures
- **Block p02 (0xFB0B)**: Status flags and binary sensors
- **Block p03 (0xFB0C)**: Additional temperatures and power values
- **Block p04 (0xFB0D)**: Extended sensor data

Each block returns multiple bytes of data that need to be decoded according to the register map.

### Write Registers

Write registers control operating parameters:

- **Command Format**: Each write register has a unique command byte
- **Offset**: 4 bytes (data starts at offset 4 in response)
- **Length**: 2 bytes (data length in response)
- **Value Format**: Typically 2 bytes, big-endian or little-endian depending on register

## Data Encoding/Decoding

### Numeric Values (hex2int)

Most temperature and measurement values use signed 16-bit integers:

```python
value = int.from_bytes(data_bytes, byteorder="big", signed=True) / factor
```

- **Factor**: Scaling factor (typically 10 for temperatures, 100 for flow rates)
- **Byte Order**: Big-endian for most read registers
- **Signed**: Yes for temperatures (can be negative)

### Unsigned Values (hex)

RPM values and counts use unsigned integers:

```python
value = int.from_bytes(data_bytes, byteorder="big", signed=False)
```

### Binary Flags (bit/nbit)

Status flags are stored as individual bits:

```python
bit_value = bool((byte >> bit_number) & 0x01)
nbit_value = not bool((byte >> bit_number) & 0x01)  # Inverted
```

### Float Values (esp_mant)

Some registers use IEEE 754 floating-point format:

```python
import struct
value = struct.unpack('>f', data_bytes)[0]  # Big-endian float
```

## Byte Order Considerations

### Read Registers
- **Temperatures, pressures**: Big-endian, signed
- **RPM, counts**: Big-endian, unsigned
- **Binary flags**: Bit-level encoding

### Write Registers
- **Numbers**: Big-endian, unsigned (for most registers)
- **Switches**: Big-endian, unsigned (0 or 1)
- **Select/Time**: Little-endian, unsigned (special handling)

### Special Cases

#### SomWinMode (Summer/Winter Mode)
Values are zero-padded:
- `01` = Winter
- `02` = Summer

When decoding, ensure values are zero-padded to 2 digits:
```python
value_str = str(value).zfill(2)  # "1" -> "01"
```

#### Time Values
Time is stored as 15-minute quarters since midnight:
- Range: 0-95 (00:00 to 23:45)
- Special value: 128 (0x80) = unset/no time

```python
def time_to_quarters(t):
    if t is None:
        return 128
    return t.hour * 4 + (t.minute // 15)

def quarters_to_time(num):
    if num == 128:
        return None
    hour = num // 4
    minute = (num % 4) * 15
    return time(hour, minute)
```

#### Schedule Values
Schedules store start and end times in consecutive bytes:
- Byte 0: Start time (quarters)
- Byte 1: End time (quarters)

## Firmware Version Detection

The firmware version determines which register maps are available:

```python
firmware = await device.read_firmware_version()
# Returns: "2.06", "2.14", "4.39", "5.39", etc.
```

Different firmware versions have different available registers and may use different data formats.

## Error Handling

### Common Errors
- **Timeout**: No response from device within timeout period
- **Checksum Error**: Response checksum doesn't match calculated value
- **Invalid Data**: Response data length doesn't match expected length
- **Communication Error**: Serial port or network connection failure

### Retry Strategy
- Read operations: Retry up to 3 times with 100ms delay
- Write operations: Retry up to 2 times with 200ms delay
- Use device lock to prevent concurrent access

## Example Communication

### Reading Temperature (Block p01, offset 8, length 4)

**Request:**
```
02 00 FB 0A 00 F9 03
```

**Response:**
```
02 00 [32 bytes of data...] [CHK] 03
```

**Decode:**
```python
# Temperature at offset 8, length 4 (2 bytes)
temp_bytes = response_data[8:10]
temperature = int.from_bytes(temp_bytes, byteorder="big", signed=True) / 10
# Result: e.g., 0x00B4 = 180 / 10 = 18.0°C
```

### Writing a Number Value

**Request:**
```
02 01 [CMD_H] [CMD_L] [VALUE_H] [VALUE_L] [CHK] 03
```

**Response:**
```
02 00 [confirmation data...] [CHK] 03
```

## Implementation Notes

### Thread Safety
All device communication must be protected by a lock:

```python
async with device.lock:
    value = await device.read_value(...)
```

### Async Operations
All I/O operations should be wrapped in `hass.async_add_executor_job()` to avoid blocking the event loop.

### Data Validation
Always validate:
- Response length matches expected length
- Values are within expected ranges
- Byte order is appropriate for the register type

## References

- Original FHEM module by Immi
- Home Assistant custom component architecture
- Stiebel Eltron THZ/LWZ documentation (where available)

## Version History

- **Initial**: Documentation created based on existing implementation
- **Future**: Updates as protocol details are clarified

---

*This documentation is based on reverse-engineering and the original FHEM module. Some details may vary by device model and firmware version.*
