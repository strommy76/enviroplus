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
    import provider_collector

    return ambient_wx, provider_collector


# ── Outcomes are causes, not severities ───────────────────────────────────────


@pytest.mark.parametrize(
    "exc,expected_attr",
    [
        (sqlite3.OperationalError("database is locked"), "OUTCOME_WRITE_ERROR"),
        (sqlite3.DatabaseError("disk image malformed"), "OUTCOME_WRITE_ERROR"),
        (urllib.error.URLError("timed out"), "OUTCOME_FETCH_ERROR"),
        (KeyError("lastData"), "OUTCOME_FETCH_ERROR"),
        (RuntimeError("something else"), "OUTCOME_FETCH_ERROR"),
    ],
)
def test_failure_maps_to_the_subsystem_that_broke(collectors, exc, expected_attr):
    """A failed derived write must not be recorded as a failed fetch.

    Recording it as one would make the canonical store lie about which
    subsystem broke -- the store would show a provider outage that never
    happened.
    """
    for module in collectors:
        assert module.outcome_for_exception(exc) == getattr(module, expected_attr)


# ── Sensor dropout is a recorded fact, not an inference from nulls ────────────


def test_dropout_predicate_uses_measurements_not_field_count(collectors):
    """Field count conflated two mechanisms; presence of a measurement is the
    actual signal. A short payload that still carries outdoor data is not a
    dropout."""
    ambient, _ = collectors
    assert ambient.has_outdoor_reading({"tempf": 80.0}) is True
    assert ambient.has_outdoor_reading({"tempf": 81.3, "humidity": 64, "tempinf": 74.1})
    assert not ambient.has_outdoor_reading({"tempinf": 74.1, "humidityin": 55, "baromabsin": 29.7})
