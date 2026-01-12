"""Copy of decode_value for testing."""
import struct


def decode_value(raw: bytes, decode_type: str, factor: float = 1.0) -> int | float | bool | str:
    """Decode a raw byte value according to the specified decode type."""
    if decode_type == "hex2int":
        return int.from_bytes(raw, byteorder="big", signed=True) / factor
    if decode_type == "hex":
        return int.from_bytes(raw, byteorder="big")
    if decode_type.startswith("bit"):
        bitnum = int(decode_type[3:])
        return bool((raw[0] >> bitnum) & 0x01)
    if decode_type.startswith("nbit"):
        bitnum = int(decode_type[4:])
        return not bool((raw[0] >> bitnum) & 0x01)
    if decode_type == "esp_mant":
        mant = struct.unpack('>f', raw)[0]
        return round(mant, 3)
    
    return raw.hex()
