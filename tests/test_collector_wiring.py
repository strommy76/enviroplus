"""
--------------------------------------------------------------------------------
FILE:        test_collector_wiring.py
PATH:        ~/projects/enviroplus/tests/test_collector_wiring.py
DESCRIPTION: Tests for the collector wiring -- which arriving response maps to
             which recorded outcome, and which raised failure maps to which
             cause.

             This layer previously had no tests at all. Both collectors ran a
             while loop at module scope, so importing them started collecting
             and nothing below the import could be exercised. Every defect
             found in the second review round lived precisely here: a database
             failure recorded as a fetch failure, an empty response producing
             two records, a failed pull leaving no trace.

CHANGELOG:
2026-08-06 16:35      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import json
import sqlite3
import sys
import urllib.error

import pytest

sys.path.insert(0, "/home/pistrommy/projects")


@pytest.fixture(scope="module")
def collectors(tmp_path_factory):
    """Import the collectors against a scratch database.

    Importing is now side-effect-free apart from config/logger/DB setup, and
    SQLITE_PATH redirects that away from the live database.
    """
    import os
    db = tmp_path_factory.mktemp("wiring") / "scratch.db"
    os.environ["SQLITE_PATH"] = str(db)
    import ambient_wx
    import airnow_wx
    return ambient_wx, airnow_wx


# ── Importing a collector must not start collecting ───────────────────────────

def test_importing_a_collector_does_not_run_it(collectors):
    """The loop is behind run(); import alone must do no collecting."""
    ambient, airnow = collectors
    assert callable(ambient.run) and callable(airnow.run)


# ── Response classification ───────────────────────────────────────────────────

def test_ambient_classifies_a_full_response(collectors):
    ambient, _ = collectors
    raw = json.dumps([{"lastData": {"tempf": 81.3, "dateutc": 1}}]).encode()
    obs, outcome, detail = ambient.classify_response(raw)
    assert outcome == ambient.OUTCOME_OK and detail is None
    assert obs["tempf"] == 81.3


def test_ambient_classifies_an_empty_response(collectors):
    ambient, _ = collectors
    obs, outcome, detail = ambient.classify_response(b"[]")
    assert obs is None and outcome == ambient.OUTCOME_EMPTY and detail


def test_ambient_classifies_a_malformed_response(collectors):
    """Unparseable bytes are a distinct cause, not an empty result."""
    ambient, _ = collectors
    obs, outcome, detail = ambient.classify_response(b"<html>502 Bad Gateway")
    assert obs is None and outcome == ambient.OUTCOME_MALFORMED and detail


def test_airnow_classifies_each_shape(collectors):
    _, airnow = collectors
    assert airnow.classify_response(b'[{"AQI":20}]')[1] == airnow.OUTCOME_OK
    assert airnow.classify_response(b"[]")[1] == airnow.OUTCOME_EMPTY
    assert airnow.classify_response(b"not json")[1] == airnow.OUTCOME_MALFORMED


# ── Outcomes are causes, not severities ───────────────────────────────────────

@pytest.mark.parametrize("exc,expected_attr", [
    (sqlite3.OperationalError("database is locked"), "OUTCOME_WRITE_ERROR"),
    (sqlite3.DatabaseError("disk image malformed"), "OUTCOME_WRITE_ERROR"),
    (urllib.error.URLError("timed out"), "OUTCOME_FETCH_ERROR"),
    (KeyError("lastData"), "OUTCOME_FETCH_ERROR"),
    (RuntimeError("something else"), "OUTCOME_FETCH_ERROR"),
])
def test_failure_maps_to_the_subsystem_that_broke(collectors, exc, expected_attr):
    """A failed derived write must not be recorded as a failed fetch.

    Recording it as one would make the canonical store lie about which
    subsystem broke -- the store would show a provider outage that never
    happened.
    """
    for module in collectors:
        assert module.outcome_for_exception(exc) == getattr(module, expected_attr)


# ── Sensor dropout is a recorded fact, not an inference from nulls ────────────

def test_outdoor_dropout_is_detected(collectors):
    """A 13-field console-only payload must be recognisable as a dropout."""
    ambient, _ = collectors
    full = {"tempf": 81.3, "humidity": 64, "tempinf": 74.1}
    indoor_only = {"tempinf": 74.1, "humidityin": 55, "baromabsin": 29.7}
    assert ambient.has_outdoor_reading(full) is True
    assert ambient.has_outdoor_reading(indoor_only) is False


def test_dropout_predicate_uses_measurements_not_field_count(collectors):
    """Field count conflated two mechanisms; presence of a measurement is the
    actual signal. A short payload that still carries outdoor data is not a
    dropout."""
    ambient, _ = collectors
    assert ambient.has_outdoor_reading({"tempf": 80.0}) is True
