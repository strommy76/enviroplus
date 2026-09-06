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
from datetime import datetime, timezone

import pytest


import provider_collector as pc  # noqa: E402
from provider_contract import load_contract  # noqa: E402
from shared import raw_retention as rr  # noqa: E402
from tests.test_provider_contract import CONTRACT, PAYLOAD, _item  # noqa: E402


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
    assert collector.attempt() is True             # restatement: rewritten idempotently, still one row
    assert _rows(collector) == [("2026-09-05 14:00:00", 11)]
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_DUPLICATE]


def test_derived_row_existence_is_not_inferred_from_retention_dedup(collector, monkeypatch):
    """A failed write followed by a byte-identical arrival must still land the row."""
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.db.execute("ALTER TABLE aq RENAME TO aq_gone")
    collector.run(_stop_after_first_attempt(), sleep=lambda s: None)      # write_error
    collector.db.execute("ALTER TABLE aq_gone RENAME TO aq")
    assert collector.attempt() is True                                    # retention says duplicate; row still written
    assert _rows(collector) == [("2026-09-05 14:00:00", 11)]
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_WRITE_ERROR, rr.OUTCOME_DUPLICATE]


def test_provider_revision_overwrites_the_derived_row(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.attempt()
    revised = [dict(i, nowcastAQI=i["nowcastAQI"] + 5) for i in PAYLOAD]
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(revised).encode())
    assert collector.attempt() is True
    assert _rows(collector) == [("2026-09-05 14:00:00", 16)]        # latest statement, one row
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_OK]            # both statements retained


def test_unparseable_body_is_recorded_exactly_once(collector, monkeypatch, caplog):
    monkeypatch.setattr(collector, "fetch", lambda: b"<html>rate limited</html>")
    with caplog.at_level(logging.ERROR, logger="test_acme"):
        assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_MALFORMED] and _rows(collector) == []
    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.parametrize("body", [b"0", b"false", b'""', b"null", b"{}", b'{"error": "rate limited"}', b"[1, 2]"])
def test_non_list_bodies_are_malformed_not_empty_and_recorded_once(collector, monkeypatch, body):
    monkeypatch.setattr(collector, "fetch", lambda: body)
    assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_MALFORMED] and _rows(collector) == []


def test_out_of_shape_payload_is_logged_at_error(collector, monkeypatch, caplog):
    monkeypatch.setattr(collector, "fetch", lambda: b'[{"WebServiceError": [{"Message": "x"}]}]')
    with caplog.at_level(logging.ERROR, logger="test_acme"):
        collector.attempt()
    assert any("declared projection not satisfied" in r.getMessage() and r.levelno == logging.ERROR
               for r in caplog.records)


def test_write_failure_after_a_partial_arrival_keeps_both_facts(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD[:2]).encode())
    collector.db.execute("DROP TABLE aq")
    collector.run(_stop_after_first_attempt(), sleep=lambda s: None)
    assert _outcomes() == [rr.OUTCOME_PARTIAL, rr.OUTCOME_WRITE_ERROR]


def test_empty_list_is_recorded_and_nothing_is_written(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: b"[]")
    assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_EMPTY] and _rows(collector) == []


def test_shape_outside_the_contract_is_malformed_with_no_row(collector, monkeypatch):
    renamed = [{("parameter" if k == "parameterName" else k): v for k, v in i.items()} for i in PAYLOAD]
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(renamed).encode())
    assert collector.attempt() is False
    assert _outcomes() == [rr.OUTCOME_MALFORMED]      # one arrival, one outcome, payload retained under it
    assert _rows(collector) == []


def test_absent_parameter_writes_the_row_and_records_partial(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD[:2]).encode())
    assert collector.attempt() is True
    assert _outcomes() == [rr.OUTCOME_PARTIAL]         # the arrival itself carries the partial outcome
    assert collector.db.execute("SELECT pm10_aqi FROM aq").fetchone() == (None,)   # never stated


def test_a_later_statement_that_omits_a_parameter_keeps_the_earlier_value(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.attempt()                                                          # pm25 11, pm10 3, ozone 22
    later = [dict(_item("PM2.5", 14)), dict(_item("OZONE", 25))]                 # PM10 not stated this time
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(later).encode())
    assert collector.attempt() is True
    assert collector.db.execute("SELECT pm25_aqi, pm10_aqi, ozone_aqi FROM aq").fetchone() == (14, 3, 25)
    assert _outcomes() == [rr.OUTCOME_OK, rr.OUTCOME_PARTIAL]


def test_a_later_statement_of_null_overwrites_the_earlier_value(collector, monkeypatch):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.attempt()
    later = [dict(i, nowcastAQI=None) if i["parameterName"] == "PM10" else i for i in PAYLOAD]
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(later).encode())
    collector.attempt()
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


def test_ensure_table_refuses_a_storage_class_or_primary_key_disagreement(collector):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aq (ts INTEGER PRIMARY KEY, pm25_aqi INTEGER, pm25_category TEXT, pm10_aqi INTEGER,"
               " pm10_category TEXT, ozone_aqi INTEGER, ozone_category TEXT, reporting_area TEXT, local_time_zone TEXT)")
    with pytest.raises(Exception, match="'ts' is INTEGER PRIMARY KEY; contract declares TEXT PRIMARY KEY"):
        pc.ensure_table(db, collector.contract)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aq (ts TEXT, pm25_aqi INTEGER, pm25_category TEXT, pm10_aqi INTEGER,"
               " pm10_category TEXT, ozone_aqi INTEGER, ozone_category TEXT, reporting_area TEXT, local_time_zone TEXT)")
    with pytest.raises(Exception, match="'ts' is TEXT; contract declares TEXT PRIMARY KEY"):
        pc.ensure_table(db, collector.contract)


def test_build_requires_the_env_file_to_carry_sqlite_path(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ACME_LAT=1\n")
    monkeypatch.delenv("SQLITE_PATH", raising=False)
    with pytest.raises(Exception, match="SQLITE_PATH"):
        pc.build(str(tmp_path / "missing.json"), env_path=str(env))


# ── Replay: the derived table is rebuildable from retention by the same path ─

def _days_today():
    return [datetime.now(timezone.utc).strftime("%Y-%m-%d")]


def test_replay_reproduces_the_live_table_by_the_same_path(collector, monkeypatch, tmp_path):
    arrivals = [PAYLOAD,                                                   # ok
                PAYLOAD,                                                   # identical -> duplicate, no payload retained
                [dict(_item("PM2.5", 14)), dict(_item("OZONE", 25))],        # partial (PM10 unstated)
                [dict(i, nowcastAQI=None) if i["parameterName"] == "PM10" else i for i in PAYLOAD],   # null statement
                [{"WebServiceError": [{"Message": "x"}]}]]                 # malformed
    for payload in arrivals:
        monkeypatch.setattr(collector, "fetch", lambda p=payload: json.dumps(p).encode())
        collector.attempt()
    live = collector.db.execute("SELECT * FROM aq ORDER BY ts").fetchall()
    retention_before = _outcomes()

    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    replayer = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("test_replay"))
    summary = replayer.replay(["2026-09-05"], today=_days_today()[0])   # the observation date PAYLOAD states

    assert rebuilt.execute("SELECT * FROM aq ORDER BY ts").fetchall() == live
    assert summary == {"provider": "acme", "days": ["2026-09-05"], "capture_days_scanned": summary["capture_days_scanned"],
                       "records": 5, "without_payload": 1, "projected": 4, "other_dates": 0, "written": 3,
                       "ok": 2, "partial": 1, "empty": 0, "malformed": 1, "reclassified": 0}
    assert _outcomes() == retention_before                                 # replay never writes retention


def test_replay_is_idempotent_and_the_latest_statement_wins_in_capture_order(collector, monkeypatch, tmp_path):
    for aqi in (11, 16):
        monkeypatch.setattr(collector, "fetch", lambda a=aqi: json.dumps([dict(_item("PM2.5", a))]).encode())
        collector.attempt()
    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    replayer = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("test_replay"))
    first = replayer.replay(["2026-09-05"])
    rows = rebuilt.execute("SELECT ts, pm25_aqi FROM aq").fetchall()
    second = replayer.replay(["2026-09-05"])
    assert rows == [("2026-09-05 14:00:00", 16)]
    assert rebuilt.execute("SELECT ts, pm25_aqi FROM aq").fetchall() == rows
    assert first["written"] == 2 and second["written"] == 2               # idempotent upsert: same rows, same result


def test_replay_counts_a_retained_outcome_that_content_no_longer_earns(collector, monkeypatch, tmp_path):
    """A retained outcome is a proxy; the replay re-derives it from the bytes."""
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.attempt()
    rr.record_outcome("acme", rr.OUTCOME_FETCH_ERROR, detail="simulated")     # no payload: skipped
    # a payload retained under 'ok' by an earlier contract that the current contract cannot project
    rr.retain("acme", json.dumps([{"ParameterName": "PM2.5", "AQI": 5}]).encode(), outcome=rr.OUTCOME_OK)
    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    summary = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("t")).replay(["2026-09-05"])
    assert summary["records"] == 3 and summary["without_payload"] == 1
    assert summary["malformed"] == 1 and summary["reclassified"] == 1 and summary["written"] == 1


def test_replay_of_a_date_with_no_retention_is_empty_not_an_error(collector):
    assert collector.replay(["1999-01-01"], today="1999-01-03")["records"] == 0


def test_cli_replay_prints_one_summary_line_and_exits(collector, monkeypatch, capsys):
    monkeypatch.setattr(pc, "build", lambda path: collector)
    pc.main(["--contract", "x.json", "--replay", "1999-01-01"])
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and json.loads(out[0])["days"] == ["1999-01-01"]


def test_replay_selects_by_observation_date_so_a_later_capture_day_still_wins(collector, monkeypatch, tmp_path):
    """The inherent date controls: a revision of hour 19 captured after the UTC-day boundary belongs to the
    observation day and is replayed with it, so a single-day replay cannot regress the row."""
    import datetime as dt
    real = rr.datetime
    class Clock(dt.datetime):
        _now = dt.datetime(2026, 9, 5, 23, 39, tzinfo=dt.timezone.utc)
        @classmethod
        def now(cls, tz=None): return cls._now
    monkeypatch.setattr(rr, "datetime", Clock)
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 11, hour="19:00")]).encode())
    collector.attempt()                                                       # captured 2026-09-05Z
    Clock._now = dt.datetime(2026, 9, 6, 0, 9, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 13, hour="19:00")]).encode())
    collector.attempt()                                                       # revision captured 2026-09-06Z
    monkeypatch.setattr(rr, "datetime", real)
    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    summary = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("t")).replay(
        ["2026-09-05"], today="2026-09-07")                                  # one observation day requested
    assert summary["capture_days_scanned"] == 4 and summary["records"] == 2 and summary["written"] == 2   # 09-04..09-07
    assert rebuilt.execute("SELECT pm25_aqi FROM aq").fetchone() == (13,)       # the later statement wins


def test_replay_leaves_statements_about_other_dates_alone(collector, monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 11, date="2026-09-05")]).encode())
    collector.attempt()
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 12, date="2026-09-06")]).encode())
    collector.attempt()
    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    summary = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("t")).replay(["2026-09-06"])
    assert summary["other_dates"] == 1 and summary["written"] == 1
    assert rebuilt.execute("SELECT ts FROM aq").fetchall() == [("2026-09-06 14:00:00",)]


def test_replay_counts_an_empty_arrival_as_empty_not_malformed(collector, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(collector, "fetch", lambda: b"[]")
    collector.attempt()
    rebuilt = sqlite3.connect(tmp_path / "rebuilt.db")
    pc.ensure_table(rebuilt, collector.contract)
    with caplog.at_level(logging.INFO, logger="t"):
        summary = pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("t")).replay(_days_today())
    assert summary["empty"] == 1 and summary["malformed"] == 0 and summary["reclassified"] == 0
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)


def test_replay_repairs_a_row_the_live_write_lost(collector, monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps(PAYLOAD).encode())
    collector.db.execute("ALTER TABLE aq RENAME TO aq_gone")
    collector.run(_stop_after_first_attempt(), sleep=lambda s: None)          # retained ok, derived write_error
    collector.db.execute("ALTER TABLE aq_gone RENAME TO aq")
    assert _rows(collector) == []
    summary = collector.replay(["2026-09-05"])
    assert summary["written"] == 1 and _rows(collector) == [("2026-09-05 14:00:00", 11)]


def test_cli_replay_refuses_a_day_that_is_not_a_utc_day(collector, monkeypatch, capsys):
    monkeypatch.setattr(pc, "build", lambda path: collector)
    for bad in ("../acme/2026-09-06", "2026-13-01", "nonsense"):
        with pytest.raises(SystemExit):
            pc.main(["--contract", "x.json", "--replay", bad])
        assert "not a UTC day" in capsys.readouterr().err
    assert pc._utc_day("2026-9-6") == "2026-09-06"      # a real day, normalized to the day-file name


def test_replay_of_two_observation_days_is_order_independent_when_their_captures_start_on_different_days(collector, monkeypatch, tmp_path):
    import datetime as dt
    real = rr.datetime
    class Clock(dt.datetime):
        _now = dt.datetime(2026, 9, 6, 15, 0, tzinfo=dt.timezone.utc)
        @classmethod
        def now(cls, tz=None): return cls._now
    monkeypatch.setattr(rr, "datetime", Clock)
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 6, date="2026-09-06")]).encode())
    collector.attempt()                                                       # obs A captured 09-06
    Clock._now = dt.datetime(2026, 9, 8, 15, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(collector, "fetch", lambda: json.dumps([_item("PM2.5", 8, date="2026-09-08")]).encode())
    collector.attempt()                                                       # obs B captured 09-08
    monkeypatch.setattr(rr, "datetime", real)
    for order in (["2026-09-06", "2026-09-08"], ["2026-09-08", "2026-09-06"]):
        rebuilt = sqlite3.connect(":memory:")
        pc.ensure_table(rebuilt, collector.contract)
        pc.Collector(contract=collector.contract, db=rebuilt, log=logging.getLogger("t")).replay(order, today="2026-09-09")
        assert rebuilt.execute("SELECT ts, pm25_aqi FROM aq ORDER BY ts").fetchall() == [
            ("2026-09-06 14:00:00", 6), ("2026-09-08 14:00:00", 8)]


def test_replay_scans_one_capture_day_before_the_named_day(collector):
    """A provider east of UTC can state a date that is captured on the previous UTC day."""
    summary = collector.replay(["2026-09-05"], today="2026-09-05")
    assert summary["capture_days_scanned"] == 2


def test_replay_refuses_an_observation_day_after_today(collector):
    with pytest.raises(Exception, match="after today"):
        collector.replay(["2999-01-01"])
