"""Pytest configuration and fixtures."""
import sys
from unittest.mock import MagicMock

# Mock Home Assistant modules
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.helpers.entity_platform'] = MagicMock()
sys.modules['homeassistant.helpers.typing'] = MagicMock()
sys.modules['homeassistant.helpers.device_registry'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.components.switch'] = MagicMock()
sys.modules['homeassistant.components.number'] = MagicMock()
sys.modules['homeassistant.components.select'] = MagicMock()
sys.modules['homeassistant.components.time'] = MagicMock()
sys.modules['homeassistant.components.schedule'] = MagicMock()
sys.modules['homeassistant.components.calendar'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['homeassistant.helpers.area_registry'] = MagicMock()
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()
sys.modules['voluptuous'] = MagicMock()
