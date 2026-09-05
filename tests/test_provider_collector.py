"""
--------------------------------------------------------------------------------
FILE:        test_provider_collector.py
PATH:        ~/projects/enviroplus/tests/test_provider_collector.py
DESCRIPTION: Collector wiring: which arriving response maps to which recorded
             outcome and derived write, against a scratch database and the
             isolated retention root.

CHANGELOG:
2026-09-05 17:40      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, "/home/pistrommy/projects")

import provider_collector as pc  # noqa: E402
from provider_contract import load_contract  # noqa: E402
from shared import raw_retention as rr  # noqa: E402
from tests.test_provider_contract import CONTRACT, PAYLOAD  # noqa: E402


@pytest.fixture
def collector(tmp_path, monkeypatch):
    monkeypatch.setenv("ACME_LAT", "1.5")
    monkeypatch.setenv("ACME_KEY", "not-a-real-key")
    monkeypatch.setenv("ACME_POLL_S", "1800")
    path = tmp_path / "acme.json"
    path.write_text(json.dumps(CONTRACT))
    contract = load_contract(path)
    rr.configure(tmp_path / "raw")
    db = sqlite3.connect(tmp_path / "scratch.db")
    pc.ensure_table(db, contract)
    return pc.Collector(contract=contract, db=db, log=logging.getLogger("test_acme"))


def _outcomes():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [outcome for _, outcome, _ in rr.read_day("acme", day)]


def _stop_after_first_attempt():
    """is_shutting_down() that admits exactly one pass through the loop."""
    calls = {"n": 0}

    def is_shutting_down():
        calls["n"] += 1
        return calls["n"] > 1
    return is_shutting_down


def _rows(collector):
    return collector.db.execute("SELECT ts, pm25_aqi FROM aq ORDER BY ts").fetchall()


def test_importing_the_collector_does_not_run_it():
    assert callable(pc.main) and callable(pc.build)


def test_ok_response_is_retained_and_written_once(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    assert collector.attempt() is True
    assert collector.attempt() is False            # same PK: or_ignore, not a second row
    assert _rows(collector) == [("2026-09-05 14:00:00", 11)]
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_DUPLICATE]


def test_unparseable_body_is_recorded_exactly_once(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: b"<html>rate limited</html>")
    with pytest.raises(rr.OutcomeAlreadyRecorded):
        collector.attempt()
    assert _outcomes() == [rr.OUTCOME_MALFORMED] and _rows(collector) == []


def test_empty_list_is_recorded_and_nothing_is_written(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: b"[]")
    assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_EMPTY] and _rows(collector) == []


def test_shape_outside_the_contract_is_malformed_with_no_row(collector, monkeypatch):
    renamed = [{("parameter" if k == "parameterName" else k): v for k, v in i.items()} for i in PAYLOAD]
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(renamed).encode())
    assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_MALFORMED]   # arrived ok; projection refused
    assert _rows(collector) == []


def test_absent_parameter_writes_the_row_and_records_partial(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD[:2]).encode())
    assert collector.attempt() is True
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_PARTIAL]
    assert collector.db.execute("SELECT pm10_aqi FROM aq").fetchone() == (None,)


def test_write_failure_is_recorded_as_a_write_error(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.db.execute("DROP TABLE aq")
    collector.run(_stop_after_first_attempt(), sleep=lambda s: None)
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_WRITE_ERROR]


def test_fetch_failure_is_recorded_as_a_fetch_error(collector, monkeypatch):
    def boom():
        raise OSError("connection reset")
    monkeypatch.setattr(collector, "fetch", boom)
    collector.run(_stop_after_first_attempt(), sleep=lambda s: None)
    assert _outcomes() == [rr.OUTCOME_FETCH_ERROR]


def test_run_stops_promptly_when_shutdown_is_requested(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: b"[]")
    calls = []
    state = {"n": 0}

    def is_shutting_down():
        state["n"] += 1
        return state["n"] > 3
    collector.run(is_shutting_down, sleep=calls.append)
    assert len(calls) < collector.contract.poll_s      # did not sleep the whole poll interval


def test_ensure_table_adds_declared_columns_to_an_existing_table(collector):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aq (ts TEXT PRIMARY KEY, pm25_aqi INTEGER, pm25_category TEXT, pm10_aqi INTEGER,"
               " pm10_category TEXT, ozone_aqi INTEGER, ozone_category TEXT, reporting_area TEXT)")
    db.execute("INSERT INTO aq (ts, pm25_aqi) VALUES ('2026-01-01 00:00:00', 5)")
    pc.ensure_table(db, collector.contract)
    assert db.execute("SELECT local_time_zone FROM aq").fetchone() == (None,)   # not captured, stated as such


def test_ensure_table_refuses_a_table_with_undeclared_columns(collector):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aq (ts TEXT PRIMARY KEY, legacy_flag INTEGER)")
    with pytest.raises(Exception, match="legacy_flag"):
        pc.ensure_table(db, collector.contract)
