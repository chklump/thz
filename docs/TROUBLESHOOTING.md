# THZ Integration - Troubleshooting Guide

This guide helps diagnose and resolve common issues with the THZ Home Assistant integration.

## Table of Contents

- [Connection Issues](#connection-issues)
- [Entity Issues](#entity-issues)
- [Data Issues](#data-issues)
- [Performance Issues](#performance-issues)
- [Diagnostics](#diagnostics)
- [Common Error Messages](#common-error-messages)

## Connection Issues

### Integration Won't Connect

**Symptoms:**
- Setup fails during initial configuration
- "Failed to connect" error message
- Integration shows as "unavailable"

**USB Connection Troubleshooting:**

1. **Verify USB Device Path**
   ```bash
   ls -l /dev/ttyUSB*
   ```
   - Common paths: `/dev/ttyUSB0`, `/dev/ttyUSB1`
   - Ensure Home Assistant has permission to access the device

2. **Check USB Permissions**
   ```bash
   # Add user to dialout group (for Home Assistant OS)
   sudo usermod -a -G dialout homeassistant
   ```

3. **Verify Baud Rate**
   - Default is 115200
   - Check your device manual for the correct baud rate
   - Try common alternatives: 9600, 19200, 38400, 57600

4. **Test with Another USB Port**
   - Some USB hubs or ports may have compatibility issues
   - Try a direct connection to the host

**Network (ser2net) Connection Troubleshooting:**

1. **Verify Network Connectivity**
   ```bash
   ping <heat_pump_ip>
   telnet <heat_pump_ip> 2323
   ```

2. **Check ser2net Configuration**
   - Default port is 2323
   - Ensure ser2net is running: `systemctl status ser2net`
   - Verify ser2net.conf has correct serial port settings

3. **Firewall Issues**
   - Check if port 2323 is open
   - Temporarily disable firewall to test

4. **Network Stability**
   - Ensure stable network connection
   - Check for packet loss or high latency

### Connection Drops Randomly

**Symptoms:**
- Entities show "unavailable" intermittently
- Connection works initially but stops

**Solutions:**

1. **Check Polling Intervals**
   - Reduce polling frequency if too aggressive
   - Default is 60 seconds per block
   - Increase to 90-120 seconds if having issues

2. **Network Stability (ser2net)**
   - Use wired connection instead of WiFi when possible
   - Check router logs for connection drops
   - Ensure ser2net device has stable power

3. **USB Cable Quality**
   - Use a high-quality, shielded USB cable
   - Keep cable length under 5 meters
   - Avoid cable near power lines or electrical interference

## Entity Issues

### Entities Not Appearing

**Symptoms:**
- Integration loads but shows few or no entities
- Expected sensors missing

**Solutions:**

1. **Check Entity Registry**
   - Go to: **Settings** → **Devices & Services** → **THZ** → **Device**
   - Click "Show disabled entities" at bottom
   - Enable any needed entities

2. **Verify Firmware Compatibility**
   - Check logs for firmware version detection
   - Ensure your firmware version is supported (206, 214, 439, 539)
   - Some entities may only exist on certain firmware versions

3. **Check Coordinator Data**
   - Download diagnostics (see below)
   - Verify coordinators have data
   - Check if specific blocks are failing

### Entity Values Not Updating

**Symptoms:**
- Entities exist but show stale data
- "Last updated" timestamp is old

**Solutions:**

1. **Check Coordinator Status**
   ```yaml
   # Check coordinator update interval in diagnostics
   # Verify last_update_success is true
   ```

2. **Increase Update Interval**
   - Some devices may struggle with fast polling
   - Try increasing interval to 120 seconds

3. **Check Device Lock Issues**
   - Too many entities polling at once can cause lock contention
   - Review logs for "timeout" or "lock" errors

### Climate Entity Not Working

**Symptoms:**
- Climate entity shows but can't control temperature
- Temperature changes don't take effect

**Solutions:**

1. **Verify Parameter Availability**
   - Check logs for "Parameter not found" errors
   - Ensure your firmware supports the parameters
   - HC2 entities require second heating circuit

2. **Check Write Permissions**
   - Some parameters may be read-only in certain modes
   - Verify heat pump is not in locked/service mode

3. **Wait for Sync**
   - Changes may take 1-2 polling cycles to reflect
   - Default delay is 60 seconds

## Data Issues

### Incorrect Sensor Values

**Symptoms:**
- Temperature readings seem wrong
- Values don't match heat pump display

**Solutions:**

1. **Check Unit Conversion**
   - Verify sensor uses correct units (°C vs °F)
   - Check if scaling factor is correct in register maps

2. **Verify Decode Type**
   - Different firmware versions may use different encoding
   - Check register maps for your firmware version

3. **Compare with Display**
   - Note exact values from heat pump display
   - Report discrepancies as GitHub issue with firmware version

### Sensors Show "Unknown" or "Unavailable"

**Symptoms:**
- Entities exist but show no value

**Solutions:**

1. **Check Data Length**
   - Coordinator data may be too short
   - Check logs for "Not enough data" warnings

2. **Verify Register Offset**
   - Register mapping may be incorrect for your firmware
   - Check register maps match your device

3. **Wait for First Update**
   - New entities need one polling cycle
   - Wait 60-120 seconds after enabling

## Performance Issues

### High CPU Usage

**Symptoms:**
- Home Assistant CPU usage high
- System sluggish

**Solutions:**

1. **Reduce Polling Frequency**
   - Increase update interval to 120-180 seconds
   - Disable unnecessary entities

2. **Reduce Entity Count**
   - Keep only needed entities enabled
   - Disable HC2 entities if not used
   - Disable advanced parameter entities (p13+)

3. **Check for Stuck Coordinators**
   - Review diagnostics for failed coordinators
   - Restart integration if needed

### Slow Response Times

**Symptoms:**
- Entity updates take long time
- Control actions delayed

**Solutions:**

1. **Check Network Latency** (ser2net only)
   ```bash
   ping -c 10 <heat_pump_ip>
   ```

2. **Reduce Concurrent Operations**
   - Avoid controlling multiple entities simultaneously
   - Add delays between automation actions

3. **Optimize Polling**
   - Use different intervals for different block types
   - Poll critical blocks more frequently
   - Poll configuration blocks less frequently

## Diagnostics

### Downloading Diagnostics

1. Go to **Settings** → **Devices & Services**
2. Find **THZ** integration
3. Click on the device
4. Click **Download Diagnostics** button (three dots menu)
5. Save the JSON file

### What Diagnostics Include

- Device information (firmware, connection type)
- Coordinator states and update status
- Entity counts (total, enabled, disabled)
- Connection parameters (redacted)
- Last update times and success status

### Analyzing Diagnostics

**Check Coordinator Health:**
```json
"coordinators": {
  "pxx0100": {
    "last_update_success": true,
    "data_available": true
  }
}
```
- `last_update_success: false` indicates communication problems
- `data_available: false` means no data received

**Check Entity Counts:**
```json
"entities": {
  "total": 150,
  "enabled": 45,
  "disabled": 105
}
```
- Unusually low counts may indicate detection issues

## Common Error Messages

### "Timeout reading from device"

**Cause:** Device not responding within timeout period

**Solutions:**
- Increase timeout in device configuration
- Check physical connection
- Verify device is powered on
- Reduce polling frequency

### "Error reading block pxx0100"

**Cause:** Specific data block cannot be read

**Solutions:**
- Check if block exists on your firmware version
- Verify register map compatibility
- Try resetting the device connection

### "Parameter not found in write manager"

**Cause:** Attempting to write to unavailable parameter

**Solutions:**
- Check firmware compatibility
- Verify parameter exists in your model
- Update to latest integration version

### "No coordinator found for block"

**Cause:** Data coordinator not initialized

**Solutions:**
- Check refresh_intervals configuration
- Verify device initialization completed
- Restart integration

### "Failed to decode sensor value"

**Cause:** Data format doesn't match expected structure

**Solutions:**
- Check register map for sensor
- Verify firmware version detection
- Report issue with diagnostics and firmware version

## Getting Help

### Before Asking for Help

1. ✅ Check this troubleshooting guide
2. ✅ Review Home Assistant logs
3. ✅ Download and review diagnostics
4. ✅ Note your firmware version
5. ✅ Try restarting the integration

### Where to Get Help

1. **GitHub Issues**: https://github.com/bigbadoooff/thz/issues
   - Bug reports
   - Feature requests
   - Firmware compatibility questions

2. **Home Assistant Community**: https://community.home-assistant.io
   - General questions
   - Automation help
   - Configuration assistance

### Information to Provide

When asking for help, include:

- **Integration version** (from manifest.json)
- **Home Assistant version**
- **Firmware version** (from device or diagnostics)
- **Connection type** (USB or network)
- **Complete error messages** from logs
- **Diagnostics file** (if relevant)
- **Steps to reproduce** the issue

### Viewing Logs

**Via UI:**
1. Go to **Settings** → **System** → **Logs**
2. Filter by "thz"

**Via Command Line:**
```bash
# Docker
docker logs homeassistant 2>&1 | grep thz

# Home Assistant OS
ha core logs | grep thz
```

**Enable Debug Logging:**
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.thz: debug
```

## Known Issues

### Issue: HC2 entities not working
**Status:** Expected behavior  
**Solution:** HC2 entities only work if you have a second heating circuit installed. Disable if not applicable.

### Issue: Calendar entities show errors
**Status:** Known limitation  
**Solution:** Calendar platform is experimental. Disable if causing issues.

### Issue: Some parameters read-only
**Status:** Device limitation  
**Solution:** Certain parameters can only be changed on the device itself or in service mode.

## Advanced Debugging

### Packet Capture (Network)

For ser2net connections:
```bash
tcpdump -i any -w thz_capture.pcap port 2323
```

### Serial Monitor (USB)

Monitor raw serial communication:
```bash
# Install screen
sudo apt-get install screen

# Monitor serial port (Ctrl+A, K to exit)
screen /dev/ttyUSB0 115200
```

### Check Register Maps

If specific parameters don't work:
1. Review `custom_components/thz/register_maps/`
2. Find your firmware version files
3. Verify register offsets and decode types
4. Report discrepancies as GitHub issue

## Contributing

Found a solution not listed here? Please:
1. Open a pull request to update this guide
2. Share in GitHub discussions
3. Help other users in community forums

## Version History

- **v0.1.0**: Added climate, binary_sensor, diagnostics platforms
- **v0.0.1**: Initial release with basic sensors and controls
