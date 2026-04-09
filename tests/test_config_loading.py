"""Verify each script's config values load from .env via require().

These tests load the real .env file and confirm every key used by the
four enviroplus scripts is present and non-empty.
"""

import os
import sys

sys.path.insert(0, "/home/pistrommy/projects")

from shared.config_service import load_env, require

# Load enviroplus .env once for all tests
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_env(_ENV_PATH, expect_key="MQTT_BROKER")


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
    def test_nws_station(self):
        val = require("NWS_STATION")
        assert val == "KCOF"

    def test_nws_user_agent(self):
        val = require("NWS_USER_AGENT")
        assert val and len(val) > 0

    def test_nws_poll_s(self):
        val = int(require("NWS_POLL_S"))
        assert val > 0


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
    def test_mqtt_broker(self):
        val = require("MQTT_BROKER")
        assert val and len(val) > 0

    def test_mqtt_port(self):
        val = int(require("MQTT_PORT"))
        assert 1 <= val <= 65535

    def test_mqtt_user(self):
        val = require("MQTT_USER")
        assert val and len(val) > 0

    def test_mqtt_key(self):
        val = require("MQTT_KEY")
        assert val and len(val) > 0
