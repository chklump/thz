# THZ Integration - Example Automations

This document provides example automations and use cases for the THZ Home Assistant integration.

## Table of Contents

- [Temperature Control](#temperature-control)
- [Alarm Notifications](#alarm-notifications)
- [Energy Optimization](#energy-optimization)
- [Comfort Schedules](#comfort-schedules)
- [System Monitoring](#system-monitoring)

## Temperature Control

### Automatically Adjust Temperature Based on Occupancy

```yaml
automation:
  - alias: "THZ: Lower temperature when away"
    trigger:
      - platform: state
        entity_id: person.home_owner
        to: "not_home"
        for:
          minutes: 30
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "eco"

  - alias: "THZ: Increase temperature when home"
    trigger:
      - platform: state
        entity_id: person.home_owner
        to: "home"
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "comfort"
```

### Night Setback

```yaml
automation:
  - alias: "THZ: Night mode temperature"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          temperature: 18
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "eco"

  - alias: "THZ: Morning comfort temperature"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          temperature: 21
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "comfort"
```

## Alarm Notifications

### Critical Alarm Notification

```yaml
automation:
  - alias: "THZ: Alarm notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.thz_alarm
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Heat Pump Alarm!"
          message: "Your THZ heat pump has an alarm. Please check immediately."
          data:
            priority: high
            tag: thz_alarm
      - service: persistent_notification.create
        data:
          title: "Heat Pump Alarm"
          message: "The heat pump has triggered an alarm at {{ now().strftime('%H:%M') }}"
          notification_id: thz_alarm
```

### Error Monitoring with History

```yaml
automation:
  - alias: "THZ: Log errors"
    trigger:
      - platform: state
        entity_id: binary_sensor.thz_error
        to: "on"
    action:
      - service: logbook.log
        data:
          name: "THZ Heat Pump"
          message: "Error detected at {{ now().strftime('%Y-%m-%d %H:%M:%S') }}"
          entity_id: binary_sensor.thz_error
      - service: notify.persistent_notification
        data:
          message: "Heat pump error detected. Check device status."
```

## Energy Optimization

### Smart Defrost Notification

```yaml
automation:
  - alias: "THZ: Defrost cycle notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.thz_defrost
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Heat Pump Defrosting"
          message: "Defrost cycle started. This is normal operation."
          data:
            tag: thz_defrost
            
  - alias: "THZ: Extended defrost warning"
    trigger:
      - platform: state
        entity_id: binary_sensor.thz_defrost
        to: "on"
        for:
          minutes: 15
    action:
      - service: notify.mobile_app
        data:
          title: "Extended Defrost Cycle"
          message: "Defrost cycle has been running for 15+ minutes. This may indicate an issue."
          data:
            priority: high
```

### Compressor Runtime Tracking

```yaml
automation:
  - alias: "THZ: Track compressor runtime"
    trigger:
      - platform: state
        entity_id: binary_sensor.thz_compressor_running
        to: "on"
    action:
      - service: counter.increment
        target:
          entity_id: counter.thz_compressor_starts

  - alias: "THZ: Daily compressor report"
    trigger:
      - platform: time
        at: "23:59:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Daily Heat Pump Report"
          message: >
            Compressor started {{ states('counter.thz_compressor_starts') }} times today.
            Average outside temp: {{ states('sensor.thz_outside_temperature') }}°C
      - service: counter.reset
        target:
          entity_id: counter.thz_compressor_starts
```

## Comfort Schedules

### Weekend vs Weekday Schedule

```yaml
automation:
  - alias: "THZ: Weekend comfort schedule"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: "off"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          temperature: 22
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "comfort"

  - alias: "THZ: Weekday eco schedule"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: "on"
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          preset_mode: "eco"
```

### Weather-Based Temperature Adjustment

```yaml
automation:
  - alias: "THZ: Adjust for cold weather"
    trigger:
      - platform: numeric_state
        entity_id: sensor.thz_outside_temperature
        below: -5
        for:
          minutes: 30
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.thz_heating_circuit_1
        data:
          temperature: 23
      - service: notify.mobile_app
        data:
          message: "Heat pump temperature increased due to cold weather ({{ states('sensor.thz_outside_temperature') }}°C)"
```

## System Monitoring

### Performance Dashboard Card

```yaml
type: entities
title: Heat Pump Status
entities:
  - entity: climate.thz_heating_circuit_1
  - entity: sensor.thz_outside_temperature
  - entity: sensor.thz_flow_temperature
  - entity: sensor.thz_return_temperature
  - entity: binary_sensor.thz_compressor_running
  - entity: binary_sensor.thz_heating_mode
  - entity: binary_sensor.thz_defrost
  - entity: binary_sensor.thz_alarm
  - entity: binary_sensor.thz_error
```

### Temperature Monitoring Graph

```yaml
type: history-graph
title: Heat Pump Temperatures
hours_to_show: 24
entities:
  - entity: sensor.thz_outside_temperature
    name: Outside
  - entity: sensor.thz_flow_temperature
    name: Flow
  - entity: sensor.thz_return_temperature
    name: Return
  - entity: sensor.thz_evaporator_temperature
    name: Evaporator
```

### System Health Check

```yaml
automation:
  - alias: "THZ: Daily health check"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - choose:
          - conditions:
              - condition: state
                entity_id: binary_sensor.thz_alarm
                state: "on"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "Heat Pump Health: ALARM"
                  message: "Your heat pump has an active alarm!"
                  data:
                    priority: high
          - conditions:
              - condition: state
                entity_id: binary_sensor.thz_error
                state: "on"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "Heat Pump Health: ERROR"
                  message: "Your heat pump has an error condition."
          - conditions:
              - condition: state
                entity_id: binary_sensor.thz_warning
                state: "on"
            sequence:
              - service: notify.mobile_app
                data:
                  title: "Heat Pump Health: Warning"
                  message: "Your heat pump has a warning condition."
        default:
          - service: notify.mobile_app
            data:
              title: "Heat Pump Health: OK"
              message: "All systems operating normally. Outside temp: {{ states('sensor.thz_outside_temperature') }}°C"
```

## Advanced: COP Calculation

```yaml
# Template sensor for basic COP estimation
template:
  - sensor:
      - name: "THZ Estimated COP"
        unit_of_measurement: ""
        state_class: measurement
        state: >
          {% set flow_temp = states('sensor.thz_flow_temperature') | float(0) %}
          {% set return_temp = states('sensor.thz_return_temperature') | float(0) %}
          {% set outside_temp = states('sensor.thz_outside_temperature') | float(0) %}
          {% if flow_temp > 0 and return_temp > 0 %}
            {# Simplified COP estimation based on temperature difference #}
            {% set temp_diff = flow_temp - return_temp %}
            {% set cop_estimate = (273 + flow_temp) / (temp_diff + 3) %}
            {{ cop_estimate | round(2) }}
          {% else %}
            0
          {% endif %}
```

## Tips

1. **Use conditions** to prevent automations from triggering unnecessarily
2. **Add delays** between related actions to allow the heat pump to respond
3. **Monitor patterns** over several days before setting aggressive automation schedules
4. **Test in eco mode first** before automating comfort settings
5. **Keep emergency overrides** - always have a way to manually control the system

## Troubleshooting

If automations aren't working:

1. Check entity IDs match your setup (`climate.thz_heating_circuit_1` may differ)
2. Verify the climate entity supports the modes you're using
3. Check Home Assistant logs for errors
4. Use **Developer Tools > States** to verify entity states
5. Download diagnostics from the integration page for support

## Contributing

Have a great automation idea? Please share it by:
1. Opening an issue on GitHub
2. Creating a pull request with your automation
3. Sharing in the Home Assistant community forums
