"""
--------------------------------------------------------------------------------
FILE:        test_env_completeness.py
PATH:        ~/projects/enviroplus/tests/test_env_completeness.py
DESCRIPTION: Enviroplus host-integration checks for its own .env completeness.

These tests load each project's .env and verify that every key the code
will call require() on is actually present. If a key is missing, the
test fails BEFORE the service does — fail-loud at test time.

CHANGELOG:
2026-08-06 11:58      Codex      [Refactor] Retire the duplicate cross-repo
                                      Stocks env scan; Stocks owns its complete
                                      env/config contract and tests.
2026-08-06 11:42      Codex      [Fix] Derive Stocks env requirements from
                                      literal shared require() calls instead of
                                      retaining the superseded pre-M7 key list.
2026-05-22 03:35      Codex      [Fix] Update Enviro+ NWS completeness checks
                                      for explicit multi-station freshness
                                      configuration.
2026-05-22 03:35      Codex      [Fix] Include NWS shutdown cadence in
                                      fail-loud Enviro+ config completeness.
2026-05-22 03:35      Codex      [Fix] Include NWS collection lookback in
                                      fail-loud Enviro+ config completeness.
--------------------------------------------------------------------------------
"""

import subprocess
from pathlib import Path

import pytest
from shared.config_service import load_env, require


class TestEnviroplusEnv:
    @pytest.fixture(autouse=True)
    def _load(self):
        root = Path(__file__).resolve().parents[1]
        common = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            text=True,
        ).strip()
        load_env(Path(common).parent / ".env", expect_key="MQTT_USER")

    def test_mqtt_credentials(self):
        assert require("MQTT_BROKER")
        assert require("MQTT_PORT")
        assert require("MQTT_USER")
        assert require("MQTT_KEY")

    def test_hardware_config(self):
        assert require("PMS5003_DEVICE")
        assert require("CONFIG_PATH")

    def test_ambient_weather(self):
        assert require("AW_API_KEY")
        assert require("AW_APP_KEY")
        assert require("AW_MAC")
        assert require("AW_POLL_S")

    def test_nws_config(self):
        assert require("NWS_API_BASE_URL")
        assert require("NWS_STATIONS")
        assert require("NWS_USER_AGENT")
        assert require("NWS_POLL_S")
        assert require("NWS_SHUTDOWN_CHECK_S")
        assert require("NWS_MAX_OBSERVATION_AGE_S")
        assert require("NWS_COLLECTION_LOOKBACK_S")

    def test_airnow_config(self):
        assert require("AIRNOW_API_KEY")
        assert require("AIRNOW_LAT")
        assert require("AIRNOW_LON")
        assert require("AIRNOW_DISTANCE")
        assert require("AIRNOW_POLL_S")
