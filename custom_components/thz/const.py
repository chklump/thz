"""Constants for the THZ integration.

This module defines configuration keys, default values, and protocol-specific
byte markers used for communication with THZ devices.

Constants:
    DOMAIN: The domain name for the THZ integration.
    SERIAL_PORT: Default serial port for USB connection.
    TIMEOUT: Default timeout value for communication.
    DATALINKESCAPE: Byte value for Data Link Escape (DLE) in protocol.
    STARTOFTEXT: Byte value for Start of Text (STX) in protocol.
    ENDOFTEXT: Byte value for End of Text (ETX) in protocol.
    CONF_CONNECTION_TYPE: Configuration key for connection type.
    CONNECTION_USB: Value representing USB connection type.
    CONNECTION_IP: Value representing IP connection type.
    DEFAULT_BAUDRATE: Default baud rate for serial communication.
    DEFAULT_PORT: Default port for IP connection.
    DEFAULT_UPDATE_INTERVAL: Default update interval in seconds.
"""

DOMAIN = "thz"
SERIAL_PORT = "/dev/ttyUSB0"
TIMEOUT = 1
DATALINKESCAPE = b"\x10"  # Data Link Escape
STARTOFTEXT = b"\x02"  # Start of Text
ENDOFTEXT = b"\x03"  # End of Text
CONF_CONNECTION_TYPE = "connection_type"
CONNECTION_USB = "usb"
CONNECTION_IP = "ip"
DEFAULT_BAUDRATE = 115200
DEFAULT_PORT = 2323
DEFAULT_UPDATE_INTERVAL = 60  # in seconds


def should_hide_entity_by_default(entity_name: str) -> bool:
    """Determine if an entity should be hidden by default.
    
    Entities are hidden if they:
    - Are related to HC2 (heating circuit 2)
    - Are time plan/program schedules
    - Are advanced technical parameters that most users don't need
    
    Args:
        entity_name: The name of the entity to check.
        
    Returns:
        True if the entity should be hidden by default, False otherwise.
    """
    name_lower = entity_name.lower()
    
    # Hide all HC2-related entities
    if "hc2" in name_lower:
        return True
    
    # Hide all time plan/program entities
    if name_lower.startswith("program"):
        return True
    
    # Hide advanced technical parameters
    # These are parameters p13-p99 which are technical settings
    # that most users don't need to adjust
    if name_lower.startswith("p") and len(name_lower) > 2:
        # Check if it starts with p followed by digits
        potential_num = name_lower[1:3]
        if potential_num.isdigit():
            param_num = int(potential_num)
            # Hide technical parameters p13 and above (gradient, hysteresis, etc.)
            if param_num >= 13:
                return True
    
    # Hide specific advanced/technical sensors
    advanced_keywords = [
        "gradient",
        "lowend",
        "roominfluence",
        "flowproportion",
        "hyst",  # Hysteresis settings
        "integral",
        "booster",
        "pasteurisation",
        "asymmetry",
    ]
    
    for keyword in advanced_keywords:
        if keyword in name_lower:
            return True
    
    return False
