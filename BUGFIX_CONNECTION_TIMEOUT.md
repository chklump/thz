# Bug Fix: ser2net Connection Timeout Issue

## Problem Description

Users reported that all sensor readings would become "unknown" after a few hours (2-4 hours typically) when using the integration with a ser2net connection. The issue would be resolved temporarily by restarting the device, but would recur after another few hours.

**Affected Setup:**
- LWZ 304 Trend heat pump
- Connection via ser2net (TCP/IP)
- Network-based serial connection

## Root Cause Analysis

The issue was caused by TCP connection timeouts in ser2net connections. The problems identified were:

1. **No TCP Keepalive**: The TCP socket did not have keepalive enabled, allowing the connection to be silently closed by the ser2net server or intermediate network devices after a period of inactivity.

2. **No Connection Health Checks**: The code did not verify that the connection was still alive before attempting to send requests.

3. **No Automatic Recovery**: When a connection was lost, there was no mechanism to automatically reconnect.

4. **Limited Error Handling**: Socket errors (connection reset, broken pipe) were caught generically without proper handling or recovery attempts.

## Solution Implemented

### 1. TCP Keepalive Configuration

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

### 2. Connection Health Check

Added `_is_connection_alive()` method that:
- Checks if socket file descriptor is valid
- Uses `MSG_PEEK` to verify socket is readable without consuming data
- Returns True only if connection is confirmed alive

### 3. Automatic Reconnection

Added `_reconnect()` method that:
- Closes the old connection gracefully
- Re-establishes connection using the original connection parameters
- Works for both USB and TCP connections

### 4. Enhanced Error Handling

Updated `_write_bytes()` and `_read_available()` to:
- Catch specific socket errors (OSError, BrokenPipeError, ConnectionError)
- Raise `ConnectionError` with descriptive messages
- Log errors at appropriate levels

### 5. Retry Logic

Updated `send_request()` to:
- Check connection health before each request
- Automatically reconnect if connection is dead
- Retry failed requests once after reconnection
- Handle `ConnectionError` exceptions gracefully

## Technical Details

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
All existing unit tests pass without modification:
- ✅ 25 tests in `test_thz_device.py`
- ✅ 18 tests in `test_protocol.py`

### Manual Verification
To verify the fix works:

1. Set up a ser2net connection with a short timeout (for testing)
2. Start Home Assistant with the integration
3. Observe that connection remains stable over the timeout period
4. Verify that sensor readings continue to update correctly
5. Check logs for keepalive messages and successful reconnections if needed

### Log Messages to Look For

**Successful Operation:**
```
INFO: TCP connection established with keepalive enabled
DEBUG: TCP keepalive enabled with idle=60s, interval=10s, count=6
```

**Connection Recovery:**
```
WARNING: Connection not alive, attempting reconnect (attempt 1/2)
WARNING: Attempting to reconnect...
INFO: Reconnection successful
```

## References

- Original Perl FHEM module: Uses periodic refresh to keep connection active
- ser2net documentation: Typically has idle timeouts of 2-4 hours
- TCP keepalive RFC: RFC 1122, Section 4.2.3.6

## Impact

This fix should resolve the "unknown data after a few hours" issue for all users with ser2net connections. USB connections are unaffected but benefit from the improved error handling and reconnection logic.
