"""
--------------------------------------------------------------------------------
FILE:        test_provider_contract.py
PATH:        ~/projects/enviroplus/tests/test_provider_contract.py
DESCRIPTION: The contract boundary: what the loader refuses, and which payload
             maps to which row or ProjectionError. Fixtures are synthetic --
             same field names as the AirNow ziplatlong endpoint, invented
             values -- because the repository is public.

CHANGELOG:
2026-09-05 17:40      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import copy
import json
import sqlite3
import sys

import pytest

sys.path.insert(0, "/home/pistrommy/projects")

from provider_contract import ContractError, ProjectionError, load_contract, project  # noqa: E402

CONTRACT = {
    "provider": "acme",
    "request": {
        "url": "https://api.example.test/current/",
        "params": {"format": {"literal": "application/json"},
                   "latitude": {"env": "ACME_LAT"}, "API_KEY": {"env": "ACME_KEY"}},
        "timeout_s": 15,
    },
    "poll_s": {"env": "ACME_POLL_S"},
    "response": {
        "pivot": {"by": "parameterName",
                  "vocabulary": {"PM2.5": "pm25", "PM10": "pm10", "OZONE": "ozone", "O3": "ozone"},
                  "columns": {"{key}_aqi": "nowcastAQI", "{key}_category": "aqiCategoryName"}},
        "row": {"ts": {"time": {"date": "dateObserved", "date_format": "%Y-%m-%d",
                                "clock": "hourObserved", "clock_format": "%H:%M"}},
                "local_time_zone": {"field": "localTimeZone"},
                "reporting_area": {"field": "reportingAreaName"}},
    },
    "store": {"table": "aq", "primary_key": "ts",
              "columns": {"ts": "TEXT", "pm25_aqi": "INTEGER", "pm25_category": "TEXT",
                          "pm10_aqi": "INTEGER", "pm10_category": "TEXT",
                          "ozone_aqi": "INTEGER", "ozone_category": "TEXT",
                          "reporting_area": "TEXT", "local_time_zone": "TEXT"}},
}


def _item(name, aqi, date="2026-09-05", hour="14:00", tz="EDT", area="Somewhere"):
    return {"dateObserved": date, "hourObserved": hour, "localTimeZone": tz,
            "reportingAreaName": area, "parameterName": name, "nowcastAQI": aqi,
            "aqiCategoryName": "Good", "siteName": "ignored", "lookupBoundary": "50 Miles"}


PAYLOAD = [_item("PM2.5", 11), _item("OZONE", 22), _item("PM10", 3)]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ACME_LAT", "1.5")
    monkeypatch.setenv("ACME_KEY", "not-a-real-key")
    monkeypatch.setenv("ACME_POLL_S", "1800")


def _write(tmp_path, doc):
    path = tmp_path / "acme.json"
    path.write_text(json.dumps(doc))
    return path


@pytest.fixture
def contract(tmp_path, env):
    return load_contract(_write(tmp_path, CONTRACT))


# ── Loader ─────────────────────────────────────────────────────────────────────

def test_loader_resolves_env_names_and_never_embeds_values_in_the_document(contract):
    assert contract.params["latitude"] == "1.5"
    assert "not-a-real-key" not in json.dumps(CONTRACT)
    assert contract.request_url() == ("https://api.example.test/current/"
                                      "?format=application%2Fjson&latitude=1.5&API_KEY=not-a-real-key")
    assert contract.poll_s == 1800


def test_loader_fails_loud_on_missing_env_key(tmp_path, env, monkeypatch):
    monkeypatch.delenv("ACME_KEY")
    with pytest.raises(Exception, match="ACME_KEY"):
        load_contract(_write(tmp_path, CONTRACT))


def test_loader_refuses_non_integer_poll(tmp_path, env, monkeypatch):
    monkeypatch.setenv("ACME_POLL_S", "soon")
    with pytest.raises(ContractError, match="poll_s"):
        load_contract(_write(tmp_path, CONTRACT))


def test_loader_refuses_unknown_op(tmp_path, env):
    doc = copy.deepcopy(CONTRACT)
    doc["response"]["row"]["reporting_area"] = {"regex": "x"}
    with pytest.raises(ContractError, match="unknown projection op"):
        load_contract(_write(tmp_path, doc))


def test_loader_refuses_produced_columns_that_are_not_declared(tmp_path, env):
    doc = copy.deepcopy(CONTRACT)
    del doc["store"]["columns"]["ozone_aqi"]
    with pytest.raises(ContractError, match="undeclared=\\['ozone_aqi'\\]"):
        load_contract(_write(tmp_path, doc))


def test_loader_refuses_declared_columns_never_produced(tmp_path, env):
    doc = copy.deepcopy(CONTRACT)
    doc["store"]["columns"]["site_name"] = "TEXT"
    with pytest.raises(ContractError, match="never_produced=\\['site_name'\\]"):
        load_contract(_write(tmp_path, doc))


def test_loader_refuses_time_op_with_undeclared_keys(tmp_path, env):
    doc = copy.deepcopy(CONTRACT)
    doc["response"]["row"]["ts"]["time"]["zone"] = "UTC"
    with pytest.raises(ContractError, match="exactly date, date_format, clock, clock_format"):
        load_contract(_write(tmp_path, doc))


def test_create_table_sql_declares_the_primary_key(contract):
    sql = contract.create_table_sql()
    assert sql.startswith("CREATE TABLE IF NOT EXISTS aq (ts TEXT PRIMARY KEY, pm25_aqi INTEGER")
    db = sqlite3.connect(":memory:")
    db.execute(sql)
    assert {r[1] for r in db.execute("PRAGMA table_info(aq)")} == set(CONTRACT["store"]["columns"])


# ── Projection: the nominal row ────────────────────────────────────────────────

def test_nominal_payload_projects_the_provider_statement_verbatim(contract):
    row, absent = project(contract, PAYLOAD)
    assert row == {"ts": "2026-09-05 14:00:00",  # stated wall-clock, not converted
                   "pm25_aqi": 11, "pm25_category": "Good",
                   "pm10_aqi": 3, "pm10_category": "Good",
                   "ozone_aqi": 22, "ozone_category": "Good",
                   "local_time_zone": "EDT",
                   "reporting_area": "Somewhere"}
    assert absent == ()


def test_both_ozone_spellings_map_to_the_ozone_columns(contract):
    row, _ = project(contract, [_item("PM2.5", 1), _item("O3", 9)])
    assert row["ozone_aqi"] == 9


def test_single_digit_hour_is_accepted_and_normalized_to_the_pk_shape(contract):
    row, _ = project(contract, [_item("PM2.5", 1, date="2026-01-05", hour="9:00", tz="EST")])
    assert row["ts"] == "2026-01-05 09:00:00" and row["local_time_zone"] == "EST"


# ── Projection: true provider states -> NULL + partial ─────────────────────────

def test_absent_declared_parameter_is_null_and_named(contract):
    row, absent = project(contract, [_item("PM2.5", 11), _item("OZONE", 22)])
    assert row["pm10_aqi"] is None and row["pm10_category"] is None
    assert absent == ("pm10_aqi", "pm10_category")


def test_null_declared_field_is_null_and_named(contract):
    row, absent = project(contract, [dict(_item("PM2.5", None), aqiCategoryName=None), _item("OZONE", 2)])
    assert row["pm25_aqi"] is None and absent == ("pm10_aqi", "pm10_category", "pm25_aqi", "pm25_category")


def test_all_declared_parameters_absent_is_not_an_observation(contract):
    payload = [_item("PM2.5", None), _item("OZONE", None), _item("PM10", None)]
    for item in payload:
        item["aqiCategoryName"] = None
    with pytest.raises(ProjectionError, match="no declared parameter present"):
        project(contract, payload)


def test_absent_non_key_field_is_null_and_named(contract):
    payload = copy.deepcopy(PAYLOAD)
    for item in payload:
        del item["reportingAreaName"]
    row, absent = project(contract, payload)
    assert row["reporting_area"] is None and absent == ("reporting_area",)


# ── Projection: outside the declared shape -> ProjectionError ──────────────────

@pytest.mark.parametrize("mutate, match", [
    (lambda p: [dict(i, parameterName="NO2") if i["parameterName"] == "PM10" else i for i in p],
     "undeclared parameterName value 'NO2'"),
    (lambda p: [{k: v for k, v in i.items() if k != "parameterName"} for i in p],
     "lacks pivot key"),
    (lambda p: p + [_item("O3", 5)], "two items resolve to store key 'ozone'"),
    (lambda p: [{("nowCastAQI" if k == "nowcastAQI" else k): v for k, v in i.items()} for i in p],
     "lacks declared field 'nowcastAQI'"),
    (lambda p: [{k: v for k, v in i.items() if k not in ("nowcastAQI", "aqiCategoryName")} for i in p],
     "lacks declared field"),
    (lambda p: [dict(i, dateObserved=None) for i in p], "must both be strings"),
    (lambda p: [dict(i, hourObserved=None) for i in p], "must both be strings"),
    (lambda p: [dict(i, dateObserved="2026-09-05 ") for i in p], "do not match declared formats"),
    (lambda p: [dict(i, hourObserved=14) for i in p], "must both be strings"),
    (lambda p: [{"WebServiceError": [{"Message": "Invalid API key"}]}], "lacks pivot key"),
    (lambda p: [], "not a non-empty list"),
    (lambda p: {"observations": p}, "not a non-empty list"),
])
def test_payload_outside_the_declared_shape_is_refused(contract, mutate, match):
    with pytest.raises(ProjectionError, match=match):
        project(contract, mutate(copy.deepcopy(PAYLOAD)))


def test_unrelated_fields_are_ignored_not_projected(contract):
    row, _ = project(contract, PAYLOAD)
    assert "siteName" not in row and "lookupBoundary" not in row
