# Bug Fix: Connection Timeout Issue (USB and ser2net)

## Problem Description

Users reported that all sensor readings would become "unknown" after a few hours (2-4 hours typically) when using the integration. The issue affected **both USB and ser2net (TCP/IP) connections**. Restarting the device would temporarily resolve the problem, but it would recur after another few hours.

**Affected Setups:**
- LWZ 304 Trend heat pump via ser2net
- USB/Serial connections
- All connection types

## Root Cause Analysis

The primary issue was **improper error handling** that affected all connection types:

1. **Silent Error Swallowing**: The `send_request()` method caught all exceptions and returned empty bytes (`b""`) instead of raising them
2. **No Error Propagation**: Errors never reached the Home Assistant coordinator, preventing proper device unavailability detection
3. **Empty Data Processing**: The coordinator received empty bytes and processed them, resulting in "unknown" sensor values
4. **No Recovery Trigger**: Since no errors were raised, Home Assistant's automatic retry/recovery mechanisms were never triggered

Secondary issues for TCP/ser2net connections:
- No TCP keepalive enabled, allowing network devices to close idle connections
- No connection health monitoring

## Solution Implemented

### 1. Proper Exception Handling (Primary Fix - Affects All Connections)

**Before:**
```python
def send_request(self, telegram: bytes, get_or_set: str) -> bytes:
    try:
        # ... communication logic ...
        return bytes(data)
    except Exception as e:
        _LOGGER.error("Error: %s", e)
        return b""  # Silently returns empty bytes!
```

**After:**
```python
def send_request(self, telegram: bytes, get_or_set: str) -> bytes:
    try:
        # ... communication logic ...
        return bytes(data)
    except ConnectionError as e:
        # Try reconnection, then raise if it fails
        raise ConnectionError(f"Connection failed: {e}") from e
    except RuntimeError as e:
        # Protocol errors - raise immediately
        raise
```

This ensures:
- Exceptions properly propagate to the Home Assistant coordinator
- Device is marked as "unavailable" (not "unknown")
- Automatic retry logic is triggered
- Reconnection attempts are made

### 2. TCP Keepalive Configuration (For ser2net)

Added TCP keepalive socket options in `_connect_tcp()`:

```python
# Enable TCP keepalive to prevent connection timeout
self.ser.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

# Configure keepalive parameters (Linux)
socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)   # Start probes after 60s idle
socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Probe every 10s
socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)     # 6 failed probes = disconnect
```

**Timing:** Connection will be detected as dead after 60s + (10s × 6) = 120 seconds of complete network failure.

### 3. Connection Health Check

Added `_is_connection_alive()` method that:
- Checks if socket/serial file descriptor is valid
- Uses `MSG_PEEK` for non-destructive connection testing (TCP)
- Checks `is_open` status (Serial)
- Uses `hasattr()` for robust type checking (works with mocked modules in tests)

### 4. Automatic Reconnection

Added `_reconnect()` method that:
- Closes dead connections gracefully
- Re-establishes connection with original parameters
- Works for both USB and TCP connections
- Raises exceptions if reconnection fails (triggers coordinator retry)

### 5. Robust Type Checking

Replaced `isinstance()` checks with `hasattr()` checks:
- More robust when modules are mocked (tests)
- Works across different implementations
- Avoids TypeErrors with mock objects

## Technical Details

### Error Flow Before Fix

```
Device Error → send_request catches → returns b"" → 
decode_response(b"") → returns None → 
read_write_register returns b"" → 
Sensors get empty data → Show as "unknown"
```

### Error Flow After Fix

```
Device Error → send_request raises exception → 
Coordinator catches UpdateFailed → 
Device marked "unavailable" → 
Coordinator retries automatically → 
Connection restored → Sensors update
```

### TCP Keepalive Parameters

The chosen parameters balance reliability and responsiveness:

- **TCP_KEEPIDLE (60s)**: Wait 60 seconds of inactivity before sending first keepalive probe
  - Long enough to avoid unnecessary probes during normal polling intervals
  - Short enough to detect issues before typical ser2net timeouts (often 2-4 hours)

- **TCP_KEEPINTVL (10s)**: Wait 10 seconds between keepalive probes
  - Standard interval for network health monitoring
  - Fast enough to detect failures quickly

- **TCP_KEEPCNT (6 probes)**: Declare connection dead after 6 failed probes
  - Total failure detection time: 60s + (10s × 6) = 120 seconds
  - Balances responsiveness with tolerance for transient network issues

### Platform Compatibility

The implementation is designed to work across platforms:
- TCP keepalive parameters are optional and wrapped in try/except
- Uses `hasattr()` to check for platform-specific constants
- Falls back gracefully on platforms without full keepalive support
- Base `SO_KEEPALIVE` works on all platforms (Windows, Linux, macOS)

## Testing

### Unit Tests
All existing unit tests updated and passing:
- ✅ 43 tests total (25 device + 18 protocol)
- ✅ Tests updated to expect exceptions instead of empty bytes
- ✅ Robust type checking works with mocked modules

### Expected Behavior After Fix

**During Normal Operation:**
- Sensors update regularly
- No "unknown" states

**During Connection Failure:**
- Sensors show as "unavailable" (not "unknown")
- Log messages indicate connection issues and reconnection attempts
- Automatic reconnection when connection is restored

### Log Messages to Look For

**Successful Operation:**
```
INFO: TCP connection established with keepalive enabled
DEBUG: TCP keepalive enabled with idle=60s, interval=10s, count=6
```

**Connection Issues:**
```
WARNING: Connection not alive, attempting reconnect (attempt 1/2)
WARNING: Attempting to reconnect...
INFO: Reconnection successful
```

**Permanent Failure:**
```
ERROR: Connection error in send_request (attempt 2/2): ...
ERROR: Connection failed after 2 attempts: ...
```

## Breaking Changes

- `send_request()` now raises exceptions instead of returning empty bytes
- `read_write_register()` raises `RuntimeError` if decoding fails
- Code that catches these exceptions may need updating (though this is internal)

## Impact

This fix resolves connection timeout issues for:
- ✅ **USB/Serial connections**: Proper error handling and recovery
- ✅ **ser2net/TCP connections**: Proper error handling + keepalive
- ✅ **All connection types**: Automatic reconnection on failure

Benefits:
- Entities show "unavailable" during failures (not "unknown")
- Automatic recovery without manual intervention
- Better logging for troubleshooting
- Robust error handling and retry logic

## References

- Original Perl FHEM module: Uses periodic refresh to keep connection active
- ser2net documentation: Typically has idle timeouts of 2-4 hours
- TCP keepalive RFC: RFC 1122, Section 4.2.3.6
- Home Assistant DataUpdateCoordinator: Handles UpdateFailed exceptions for device unavailability
