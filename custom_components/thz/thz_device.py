import asyncio  # noqa: D100
import logging
import socket
import time

import serial

from homeassistant.core import HomeAssistant

from . import const
from .register_maps.register_map_manager import (
    RegisterMapManager,
    RegisterMapManagerWrite,
)

_LOGGER = logging.getLogger(__name__)


class THZDevice:
    """Represents the connection to the THZ heat pump."""

    def __init__(
        self,
        connection: str = "usb",
        port: str | None = None,
        host: str | None = None,
        tcp_port: int | None = None,
        baudrate: int = const.DEFAULT_BAUDRATE,
        read_timeout: float = const.TIMEOUT,
    ) -> None:
        """Initialize basic configuration – no communication yet."""
        self.connection = connection
        self.port = port
        self.host = host
        self.tcp_port = tcp_port
        self.baudrate = baudrate
        self.read_timeout = read_timeout
        self._initialized = False

        # Placeholders
        self.ser: serial.Serial | socket.socket | None = None
        self._firmware_version: str | None = None
        self.register_map_manager: RegisterMapManager | None = None
        self.write_register_map_manager: RegisterMapManagerWrite | None = None
        self._cache = {}
        self._cache_duration = 60

        # Thread lock for parallel access
        self.lock = asyncio.Lock()
        self._last_access = 0
        self._min_interval = 0.1  # minimum time between reads in seconds

        # ---------------------------------------------------------------------

    async def async_initialize(self, hass: HomeAssistant) -> None:
        """Open connection and initialize firmware-dependent data structures."""
        _LOGGER.debug("Initializing THZ device (%s)", self.connection)

        # Open connection
        if self.connection == "usb":
            self._connect_serial()
        elif self.connection == "ip":
            self._connect_tcp()
        else:
            raise ValueError(f"Unknown connection type: {self.connection}")

        # Read firmware (runs synchronously in executor)
        self._firmware_version = await hass.async_add_executor_job(
            self.read_firmware_version
        )
        _LOGGER.info("Firmware version detected: %s", self._firmware_version)

        # Load firmware-specific register maps
        if self._firmware_version is None:
            raise RuntimeError("Firmware version could not be determined")
        self.register_map_manager = RegisterMapManager(self._firmware_version)
        self.write_register_map_manager = RegisterMapManagerWrite(
            self._firmware_version
        )

        self._cache = {}  # { block_name: (timestamp, payload) }
        self._cache_duration = 60  # seconds

        self._initialized = True

    def _connect_serial(self):
        """Open the USB/Serial connection."""
        _LOGGER.debug(
            "Opening serial connection: %s @ %s baud", self.port, self.baudrate
        )
        self.ser = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=self.read_timeout,
        )

    def _connect_tcp(self):
        """Connect to ser2net (TCP/IP) with keepalive enabled.
        
        Enables TCP keepalive to prevent connection timeouts when using ser2net.
        This is critical for long-running connections that may be idle between polls.
        """
        _LOGGER.debug("Opening TCP connection: %s:%s", self.host, self.tcp_port)
        self.ser = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ser.settimeout(self.read_timeout)
        
        # Enable TCP keepalive to prevent connection timeout
        # This is essential for ser2net connections that may timeout after inactivity
        self.ser.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Configure keepalive parameters (Linux-specific but safe on other platforms)
        # These settings ensure the connection stays alive even during long idle periods
        try:
            # Start sending keepalive probes after 60 seconds of inactivity
            if hasattr(socket, 'TCP_KEEPIDLE'):
                self.ser.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            # Send keepalive probes every 10 seconds
            if hasattr(socket, 'TCP_KEEPINTVL'):
                self.ser.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            # Close connection after 6 failed probes (60 seconds total)
            if hasattr(socket, 'TCP_KEEPCNT'):
                self.ser.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)
            _LOGGER.debug("TCP keepalive enabled with idle=60s, interval=10s, count=6")
        except (OSError, AttributeError) as e:
            # Keepalive parameters may not be available on all platforms
            _LOGGER.warning("Could not set TCP keepalive parameters: %s", e)
        
        self.ser.connect((self.host, self.tcp_port))
        _LOGGER.info("TCP connection established with keepalive enabled")

    def _is_connection_alive(self) -> bool:
        """Check if the connection is still alive.
        
        Uses multiple methods to verify connection health:
        1. Check if socket/serial file descriptor is valid
        2. For TCP: Try MSG_PEEK to detect closed connections
        3. For serial: Check is_open status
        
        Returns:
            bool: True if connection is alive, False otherwise
        """
        if self.ser is None:
            return False
        
        # Check if it's a socket - use hasattr to avoid issues with mocks
        if hasattr(self.ser, 'fileno') and hasattr(self.ser, 'recv'):
            # This is likely a socket
            try:
                # Check if socket is still valid
                if self.ser.fileno() == -1:
                    return False
                
                # Try a quick peek without blocking to detect closed connections
                # This is a best-effort check; MSG_PEEK may not work on all platforms
                self.ser.setblocking(False)
                try:
                    # recv with MSG_PEEK doesn't remove data from buffer
                    # Empty return on non-blocking socket just means no data available
                    self.ser.recv(1, socket.MSG_PEEK)
                except BlockingIOError:
                    # No data available but connection is alive
                    pass
                except (OSError, socket.error):
                    # Connection is broken
                    return False
                
                return True
            except (OSError, socket.error, AttributeError):
                return False
        elif hasattr(self.ser, 'is_open'):
            # This is likely a serial connection
            try:
                return self.ser.is_open
            except AttributeError:
                return False
        
        # Unknown connection type or uninitialized
        return False

    def _reconnect(self):
        """Attempt to reconnect if connection was lost."""
        _LOGGER.warning("Attempting to reconnect...")
        try:
            if self.ser is not None:
                try:
                    self.ser.close()
                except Exception:
                    pass
            
            if self.connection == "usb":
                self._connect_serial()
            elif self.connection == "ip":
                self._connect_tcp()
            
            _LOGGER.info("Reconnection successful")
        except Exception as e:
            _LOGGER.error("Reconnection failed: %s", e)
            raise

    def read_block_cached(self, block: bytes, cache_duration: float = 60) -> bytes:
        """Read a block of data with caching support.

        Args:
            block (bytes): The block identifier to read.
            cache_duration (float): The duration in seconds to cache the data.
            Defaults to 60 seconds.

        Returns:
            bytes: The block data. Returns cached data if available and not expired,
            otherwise fetches fresh data.
        """
        now = time.time()
        if block in self._cache:
            ts, data = self._cache[block]
            if now - ts < cache_duration:
                return data

        data = self.read_block(block, "get")
        self._cache[block] = (now, data)
        return data

    def send_request(self, telegram: bytes, get_or_set: str) -> bytes:
        """Send request via USB or TCP, receive response.
        
        Automatically reconnects if connection is lost.
        
        Raises:
            ConnectionError: If connection fails and reconnection is unsuccessful
            RuntimeError: If device communication fails (handshake, timeout, invalid response)
        """
        timeout = self.read_timeout
        data = bytearray()
        max_retries = 1  # Allow one retry on connection error
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Check connection health before sending (only if device was initialized)
                if self._initialized and not self._is_connection_alive():
                    _LOGGER.warning("Connection not alive, attempting reconnect (attempt %d/%d)", 
                                  attempt + 1, max_retries + 1)
                    self._reconnect()

                # 1. Send greeting (0x02)
                self._write_bytes(const.STARTOFTEXT)
                # _LOGGER.info("Greeting sent (0x02)")

                # 2. Expect 0x10 response
                response = self._read_exact(1, timeout)
                if response != const.DATALINKESCAPE:
                    error_msg = f"Handshake 1 failed, received: {response.hex() if response else 'no data'}"
                    _LOGGER.error(error_msg)
                    raise RuntimeError(error_msg)

                # 3. Send telegram
                self._reset_input_buffer()
                self._write_bytes(telegram)
                # _LOGGER.info("Request sent: %s", telegram.hex())

                # 4. Expect 0x10 0x02 response
                # Note: Device may send 0x10 and 0x02 separately with a delay
                response = self._read_exact(2, timeout)
                
                # Handle case where device sends 0x10 first, then 0x02 after delay
                if response == const.DATALINKESCAPE:
                    _LOGGER.debug("Received 0x10, waiting for 0x02...")
                    # Add delay for firmware 2.x as per Perl module
                    # Note: time.sleep() is used here instead of asyncio.sleep() because
                    # this method runs in an executor job (blocking context)
                    if self._firmware_version and self._firmware_version.startswith("2"):
                        time.sleep(0.005)
                    second_byte = self._read_exact(1, timeout)
                    if second_byte == const.STARTOFTEXT:
                        response = const.DATALINKESCAPE + const.STARTOFTEXT
                    else:
                        error_msg = f"Handshake 2 failed: received 0x10 then {second_byte.hex() if second_byte else 'no data'}"
                        _LOGGER.error(error_msg)
                        raise RuntimeError(error_msg)
                elif response == const.STARTOFTEXT:
                    # Sometimes device sends just 0x02 (as per Perl code line 1525)
                    _LOGGER.debug("Received only 0x02 as response")
                    response = const.DATALINKESCAPE + const.STARTOFTEXT  # Accept it
                
                if response != const.DATALINKESCAPE + const.STARTOFTEXT:
                    error_msg = f"Handshake 2 failed, received: {response.hex() if response else 'no data'}"
                    _LOGGER.error(error_msg)
                    raise RuntimeError(error_msg)

                if get_or_set == "get":
                    # 5. Send confirmation (0x10)
                    self._write_bytes(const.DATALINKESCAPE)

                    # 6. Receive data telegram until 0x10 0x03
                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        chunk = self._read_available()
                        if chunk:
                            data.extend(chunk)
                            if (
                                len(data) >= 8
                                and data[-2:] == const.DATALINKESCAPE + const.ENDOFTEXT
                            ):
                                break

                    # _LOGGER.info("Received raw data: %s", data.hex())

                    if not (
                        len(data) >= 8 and data[-2:] == const.DATALINKESCAPE + const.ENDOFTEXT
                    ):
                        error_msg = "No valid response received after data request - timeout or incomplete data"
                        _LOGGER.error(error_msg)
                        raise RuntimeError(error_msg)

                # 7. End of communication
                self._write_bytes(const.STARTOFTEXT)
                return bytes(data)
            
            except ConnectionError as e:
                last_error = e
                _LOGGER.error("Connection error in send_request (attempt %d/%d): %s", 
                            attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    # Try to reconnect for next attempt
                    try:
                        self._reconnect()
                        continue  # Retry after successful reconnection
                    except Exception as reconnect_error:
                        _LOGGER.error("Reconnect failed: %s", reconnect_error)
                        # Fall through to raise the original connection error
                # Re-raise the connection error after max retries
                raise ConnectionError(f"Connection failed after {max_retries + 1} attempts: {e}") from e
            
            except RuntimeError as e:
                # Protocol/handshake errors - don't retry these
                last_error = e
                _LOGGER.error("Protocol error in send_request: %s", e)
                raise
            
            except Exception as e:
                last_error = e
                _LOGGER.error("Unexpected error in send_request: %s", e)
                raise RuntimeError(f"Device communication failed: {e}") from e
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("send_request failed without specific error")

    # Helper methods
    def _write_bytes(self, data: bytes):
        """Send bytes depending on connection type.
        
        Raises:
            ConnectionError: If the connection is closed or broken
        """
        try:
            # Use hasattr to check connection type instead of isinstance
            # This is more robust when modules are mocked in tests
            if hasattr(self.ser, 'send') and hasattr(self.ser, 'recv'):
                # This is a socket
                self.ser.send(data)
            elif hasattr(self.ser, 'write') and hasattr(self.ser, 'flush'):
                # This is serial
                self.ser.write(data)
                self.ser.flush()
            else:
                raise ConnectionError("Unknown connection type")
        except (OSError, socket.error, BrokenPipeError) as e:
            # Connection reset, broken pipe, or other socket/serial errors
            _LOGGER.error("Connection error during write: %s", e)
            raise ConnectionError(f"Failed to write to connection: {e}") from e

    def _read_exact(self, size: int, timeout: float) -> bytes:
        """Read exactly n bytes, regardless of USB or TCP."""
        end_time = time.time() + timeout
        buf = bytearray()
        while len(buf) < size and time.time() < end_time:
            chunk = self._read_available()
            if chunk:
                buf.extend(chunk)
            # Note: time.sleep(0.01) was removed as it causes blocking in async context
        return bytes(buf)

    def _read_available(self) -> bytes:
        """Read available bytes.
        
        Raises:
            ConnectionError: If the connection is closed or broken
        """
        # Use hasattr to check connection type instead of isinstance
        # This is more robust when modules are mocked in tests
        if hasattr(self.ser, 'recv') and hasattr(self.ser, 'setblocking'):
            # This is a socket
            try:
                self.ser.setblocking(False)
                data = self.ser.recv(1024)
                if not data and hasattr(self.ser, 'fileno') and self.ser.fileno() == -1:
                    # Socket is closed
                    raise ConnectionError("TCP socket connection closed")
                return data
            except BlockingIOError:
                return b""
            except (OSError, socket.error) as e:
                # Connection reset, broken pipe, or other socket errors
                _LOGGER.error("TCP socket error during read: %s", e)
                raise ConnectionError(f"TCP connection error: {e}") from e
        elif hasattr(self.ser, 'in_waiting') and hasattr(self.ser, 'read'):
            # This is serial
            waiting = getattr(self.ser, "in_waiting", 0)
            if waiting > 0:
                return self.ser.read(waiting)
            return b""
        else:
            return b""

    def _reset_input_buffer(self):
        """Delete any existing input buffer.

        TCP sockets do not have an input buffer to reset, so this is only
        relevant for serial connections.
        """
        if self.ser is not None and hasattr(self.ser, "reset_input_buffer"):
            try:
                self.ser.reset_input_buffer()
            except AttributeError:
                pass

    def close(self):
        """Close the connection."""
        if self.ser is not None:
            self.ser.close()

    def thz_checksum(self, data: bytes) -> bytes:
        """Calculate THZ checksum for given data."""
        checksum = sum(b for i, b in enumerate(data) if i != 2)
        checksum = checksum % 256
        return bytes([checksum])

    def unescape(self, data: bytes) -> bytes:
        """Remove escape sequences from data."""
        # 0x10 0x10 -> 0x10
        data = data.replace(
            const.DATALINKESCAPE + const.DATALINKESCAPE, const.DATALINKESCAPE
        )
        # 0x2B 0x18 -> 0x2B
        return data.replace(b"\x2b\x18", b"\x2b")

    def escape(self, data: bytes) -> bytes:
        """Add escape sequences to data before sending.
        
        According to the protocol (from FHEM THZ module):
        - Each 0x10 byte must be escaped as 0x10 0x10
        - Each 0x2B byte must be escaped as 0x2B 0x18
        
        The order of escaping (0x10 first, then 0x2B) matches the FHEM implementation
        and is safe because these escape sequences don't interfere with each other.
        
        Args:
            data: Raw bytes to escape
            
        Returns:
            Escaped bytes ready to send
        """
        # 0x10 -> 0x10 0x10 (matches Perl line 1764)
        data = data.replace(const.DATALINKESCAPE, const.DATALINKESCAPE + const.DATALINKESCAPE)
        # 0x2B -> 0x2B 0x18 (matches Perl line 1768)
        return data.replace(b"\x2b", b"\x2b\x18")

    def decode_response(self, data: bytes):
        """Decode the response from the THZ device, checking header, CRC, and unescaping."""
        try:
            if len(data) < 6:
                _LOGGER.error("Response too short: %s", data.hex())
                return None

            data = self.unescape(data)

            # Header is the first 2 bytes
            header = data[0:2]
            if header in (b"\x01\x80", b"\x01\x00"):
                # Normal response b'\x01\x80' for "set" commands, b'\x01\x00' for "get"
                # CRC is byte 2 (index 2)
                crc = data[2]
                # Payload = between byte 3 and last 2 bytes (ETX)
                payload = data[3:-2]
                # Check CRC
                # For CRC calculation: everything except CRC and ETX (last 2 bytes)
                # Assemble hex string for checking
                check_data = data[:2] + b"\x00" + payload
                # _LOGGER.debug("Payload: %s, Checksum: %02X, Check data: %s",
                #               payload.hex(), crc, check_data.hex())
                checksum_bytes = self.thz_checksum(check_data)
                calc_crc = checksum_bytes[0]
                if calc_crc != crc:
                    _LOGGER.error(
                        "CRC error in response. Expected %02X, calculated %02X",
                        crc,
                        calc_crc,
                    )
                    return None

                return checksum_bytes + payload

            if header == b"\x01\x01":
                _LOGGER.error("Timing issue from device")
                return None
            if header == b"\x01\x02":
                _LOGGER.error("CRC error in request")
                return None
            if header == b"\x01\x03":
                _LOGGER.error("Unknown command")
                return None
            if header == b"\x01\x04":
                _LOGGER.error("Unknown register request")
                return None
            _LOGGER.error("Unknown response: %s", data.hex())
            return None
        except Exception as e:
            _LOGGER.error("Error decoding response: %s", e)
            return None

    def read_write_register(
        self,
        addr_bytes: bytes,
        get_or_set: str = "get",
        payload_to_deliver: bytes = b"",
    ) -> bytes:
        """Reads or writes a register from/to the THZ device.
        
        Raises:
            ConnectionError: If connection fails
            RuntimeError: If device communication fails
        """
        header = b"\x01\x00" if get_or_set == "get" else b"\x01\x80"
        # Standard Header für "get" und "set"
        footer = const.DATALINKESCAPE + const.ENDOFTEXT  # Standard Footer

        checksum = self.thz_checksum(header + b"\x00" + addr_bytes + payload_to_deliver)
        # b'\x00' = Platzhalter für die Checksumme
        # _LOGGER.debug(f"Berechnete Checksumme: {checksum.hex()} für Adresse {addr_bytes.hex()}
        # mit Payload {payload_to_deliver.hex()}")
        telegram = self.construct_telegram(
            addr_bytes + payload_to_deliver, header, footer, checksum
        )
        # _LOGGER.debug(f"Konstruiertes Telegramm: {telegram.hex()}")
        raw_response = self.send_request(telegram, get_or_set)
        # _LOGGER.debug(f"Rohantwort erhalten: {raw_response.hex()}")
        # _LOGGER.debug("Payload dekodiert: %s", payload.hex())
        if get_or_set == "get":
            decoded = self.decode_response(raw_response)
            if decoded is None:
                raise RuntimeError("Failed to decode device response")
            return decoded

        return b""

    def construct_telegram(
        self, addr_bytes: bytes, header: bytes, footer: bytes, checksum: bytes
    ) -> bytes:
        r"""Constructs a telegram for the THZ device based on the given address bytes.

        Args:
            addr_bytes: Address bytes including command and optional payload (e.g. b'\xfb' or b'\x0a\x01\x1f')
            header: Header bytes (e.g. b'\x01\x00' or b'\x01\x80')
            footer: Footer bytes (e.g. b'\x10\x03')
            checksum: Checksum bytes (e.g. b'\x5a')

        Returns:
            telegram ready to send.
        """
        # Escape the checksum + command (+ payload) bytes according to the protocol
        # (0x10 -> 0x10 0x10, 0x2B -> 0x2B 0x18)
        # This matches the FHEM THZ module's THZ_encodecommand() function behavior
        escaped_data = self.escape(checksum + addr_bytes)
        return header + escaped_data + footer

    def read_firmware_version(self) -> str:
        """Reads the firmware version from the THZ device.

        - Address (Register): 0xFD
        - Offset: 2
        - Length: 2 bytes
        - Interpreted as: unsigned big-endian integer
        """
        try:
            value_raw = self.read_value(b"\xfd", "get", 2, 2)
            if value_raw is None:
                _LOGGER.error("Firmware-Version konnte nicht gelesen werden: Keine Antwort")
                return ""
            # _LOGGER.debug("Rohdaten Firmware-Version: %s", value_raw.hex())
            firmware_version = int.from_bytes(value_raw, byteorder="big", signed=False)
            _LOGGER.debug("Firmware-Version gelesen: %s", firmware_version)
            return str(firmware_version)
        except Exception as e:
            _LOGGER.error(f"Firmware-Version konnte nicht gelesen werden: {e}")
            return ""

    def read_value(
        self, addr_bytes: bytes, get_or_set: str, offset: int, length: int
    ) -> bytes:
        r"""Reads a value from the THZ device.

        Args:
            addr_bytes: bytes (e.g. b'\xfb')
            get_or_set: "get" or "set"

        Returns:
            byte value read from the device
        """
        response = self.read_write_register(addr_bytes, get_or_set)
        # _LOGGER.info("Antwort von Wärmepumpe: %s", response.hex())
        # _LOGGER.info("Gelesener Wert (Offset %s, Length %s): %s", offset, length, value_raw.hex())
        return response[offset : offset + length]

    def write_value(self, addr_bytes: bytes, value: bytes) -> None:
        r"""Write a value to the THZ device.

        Args:
            addr_bytes: bytes (e.g. b'\xfb')
            value: integer value to write
        """
        self.read_write_register(addr_bytes, "set", value)
        _LOGGER.debug("Value %s written to address %s", value, addr_bytes.hex())

    def read_block(self, addr_bytes: bytes, get_or_set: str) -> bytes:
        r"""Read a block from the THZ device.

        Args:
            addr_bytes: bytes (e.g. b'\xfb')
            get_or_set: "get" or "set"

        Returns:
            block read from the device
        """
        return self.read_write_register(addr_bytes, get_or_set)

    @property
    def firmware_version(self) -> str:
        """Return the firmware version of the device."""
        if self._firmware_version is None:
            raise RuntimeError("Device not initialized or firmware version unknown")
        return self._firmware_version

    @property
    def available_reading_blocks(self) -> list[str]:
        """Return the available reading blocks of the device."""
        if self.register_map_manager:
            return list(self.register_map_manager.get_all_registers().keys())
        return []
