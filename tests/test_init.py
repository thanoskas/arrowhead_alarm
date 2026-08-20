"""Tests for ECi integration lifecycle operations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.arrowhead_alarm import (
    _resolve_firmware_info,
    async_reload_entry,
    async_unload_entry,
)
from custom_components.arrowhead_alarm.const import DOMAIN


def make_hass(entry_id="test_entry"):
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinator": MagicMock(async_shutdown=AsyncMock()),
                "client": MagicMock(disconnect=AsyncMock()),
            }
        }
    }
    return hass


def make_entry(entry_id="test_entry"):
    entry = MagicMock()
    entry.entry_id = entry_id
    return entry


def test_unload_entry_disconnects_eci_resources():
    hass = make_hass()
    entry = make_entry()
    data = hass.data[DOMAIN][entry.entry_id]

    result = asyncio.run(async_unload_entry(hass, entry))

    assert result is True
    data["coordinator"].async_shutdown.assert_awaited_once()
    data["client"].disconnect.assert_awaited_once()
    assert entry.entry_id not in hass.data[DOMAIN]


def test_reload_entry_calls_current_setup_and_unload():
    hass = MagicMock()
    entry = make_entry()

    with patch("custom_components.arrowhead_alarm.async_unload_entry", new=AsyncMock(return_value=True)) as unload, \
         patch("custom_components.arrowhead_alarm.async_setup_entry", new=AsyncMock()) as setup:
        asyncio.run(async_reload_entry(hass, entry))

    unload.assert_awaited_once_with(hass, entry)
    setup.assert_awaited_once_with(hass, entry)


def test_resolve_firmware_info_keeps_known_persisted_version_when_client_is_unknown():
    entry = MagicMock()
    entry.data = {
        "firmware_version": "10.3.51",
        "protocol_mode": 4,
        "supports_mode_4": True,
    }
    client = MagicMock()
    client.is_connected = False
    client.firmware_version = "Unknown"
    client.protocol_mode = "MODE_1"
    client.mode_4_features_active = False
    client.supports_mode_4 = False

    result = _resolve_firmware_info(entry, client)

    assert result["version"] == "10.3.51"
    assert result["protocol_mode"] == 4
    assert result["supports_mode_4"] is True


def test_resolve_firmware_info_ignores_unknown_persisted_value_when_runtime_is_real():
    entry = MagicMock()
    entry.data = {"firmware_version": "Unknown", "protocol_mode": 1, "supports_mode_4": False}
    client = MagicMock()
    client.is_connected = True
    client.firmware_version = "11.0.0"
    client.protocol_mode = "MODE_4"
    client.mode_4_features_active = True
    client.supports_mode_4 = True

    result = _resolve_firmware_info(entry, client)

    assert result["version"] == "11.0.0"
    assert result["protocol_mode"] == 4
    assert result["mode_4_active"] is True
    assert result["supports_mode_4"] is True


def test_resolve_firmware_info_does_not_overwrite_live_protocol_state():
    entry = MagicMock()
    entry.data = {
        "firmware_version": "10.3.51",
        "protocol_mode": 1,
        "supports_mode_4": False,
    }
    client = MagicMock()
    client.is_connected = True
    client.firmware_version = "10.3.51"
    client.protocol_mode = "MODE_4"
    client.supports_mode_4 = True
    client.mode_4_features_active = True

    result = _resolve_firmware_info(entry, client)

    assert result["protocol_mode"] == 4
    assert result["supports_mode_4"] is True
    assert result["mode_4_active"] is True
