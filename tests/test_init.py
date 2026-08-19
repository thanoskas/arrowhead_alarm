"""Tests for ECi integration lifecycle operations."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.arrowhead_alarm import async_reload_entry, async_unload_entry
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
