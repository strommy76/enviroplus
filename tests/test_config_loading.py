"""
--------------------------------------------------------------------------------
FILE:        test_config_loading.py
PATH:        ~/projects/enviroplus/tests/test_config_loading.py
DESCRIPTION: Verify each script's config values load from .env via require().

These tests load the real .env file and confirm every key used by the
four enviroplus scripts is present and non-empty.

CHANGELOG:
2026-05-22 03:30      Codex      [Fix] Validate the NWS multi-station
                                      freshness configuration required by the
                                      stale-observation repair.
2026-05-22 03:30      Codex      [Fix] Validate explicit NWS shutdown check
                                      cadence config.
2026-05-22 03:30      Codex      [Fix] Validate bounded NWS observation
                                      collection lookback config.
--------------------------------------------------------------------------------
"""

import os
import sys

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require

# Load enviroplus .env once for all tests
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_env(_ENV_PATH, expect_key="SQLITE_PATH")


class TestAmbientWxConfig:
    def test_aw_api_key(self):
        val = require("AW_API_KEY")
        assert val and len(val) > 0

    def test_aw_app_key(self):
        val = require("AW_APP_KEY")
        assert val and len(val) > 0

    def test_aw_mac(self):
        val = require("AW_MAC")
        assert val and len(val) > 0

    def test_aw_poll_s(self):
        val = int(require("AW_POLL_S"))
        assert val > 0


class TestNwsWxConfig:
    def test_nws_api_base_url(self):
        val = require("NWS_API_BASE_URL")
        assert val.startswith("https://")

    def test_nws_stations(self):
        stations = [station.strip() for station in require("NWS_STATIONS").split(",")]
        assert all(stations)
        assert len(stations) >= 1

    def test_nws_user_agent(self):
        val = require("NWS_USER_AGENT")
        assert val and len(val) > 0

    def test_nws_poll_s(self):
        val = int(require("NWS_POLL_S"))
        assert val > 0

    def test_nws_shutdown_check_s(self):
        val = int(require("NWS_SHUTDOWN_CHECK_S"))
        assert val > 0

    def test_nws_max_observation_age_s(self):
        val = int(require("NWS_MAX_OBSERVATION_AGE_S"))
        assert val > 0

    def test_nws_collection_lookback_s(self):
        val = int(require("NWS_COLLECTION_LOOKBACK_S"))
        assert val >= int(require("NWS_MAX_OBSERVATION_AGE_S"))


class TestAirnowWxConfig:
    def test_airnow_api_key(self):
        val = require("AIRNOW_API_KEY")
        assert val and len(val) > 0

    def test_airnow_lat(self):
        val = float(require("AIRNOW_LAT"))
        assert -90 <= val <= 90

    def test_airnow_lon(self):
        val = float(require("AIRNOW_LON"))
        assert -180 <= val <= 180

    def test_airnow_distance(self):
        val = int(require("AIRNOW_DISTANCE"))
        assert val > 0

    def test_airnow_poll_s(self):
        val = int(require("AIRNOW_POLL_S"))
        assert val > 0


class TestEnviroDashConfig:
    """Assert the keys enviro_dash3 actually depends on.

    These previously asserted the MQTT credentials. That made the suite a
    monument to a removed integration rather than a referee for the live one:
    it went green while pinning secrets nothing read, and deleting those secrets
    would have errored the whole module at collection.
    """

    def test_sqlite_path(self):
        val = require("SQLITE_PATH")
        assert val and val.endswith(".db")

    def test_log_path(self):
        val = require("LOG_PATH")
        assert val and len(val) > 0

    def test_config_path(self):
        val = require("CONFIG_PATH")
        assert val and val.endswith(".json")
