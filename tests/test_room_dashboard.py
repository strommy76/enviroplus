"""Owned dashboard query/config contracts; does not emulate Grafana rendering."""

import json
import sqlite3
from pathlib import Path


def test_room_stats_keep_trailing_null_and_indoor_chart_keeps_gaps():
    root = Path(__file__).resolve().parents[1]
    home = json.loads((root / "grafana/dashboards/home.json").read_text())
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE readings (ts TEXT, temp_f REAL, humidity REAL)")
    db.executemany(
        "INSERT INTO readings VALUES (?, ?, ?)",
        [("2026-10-30 00:00:00", 76.1, 45.0), ("2026-10-30 00:01:00", None, None)],
    )
    for title, expected in [("Indoor Temp", 76.1), ("Indoor Humidity", 45.0)]:
        panel = next(p for p in home["panels"] if p["title"] == title)
        sql = (
            panel["targets"][0]["rawQueryText"]
            .replace("$__from", "1793318400000")
            .replace("$__to", "1793318520000")
        )
        values = [r[1] for r in db.execute(sql)]
        assert values == [expected, None]
        assert panel["options"]["reduceOptions"]["calcs"] == ["last"]
    indoor = [
        p
        for p in home["panels"]
        if any('AS "Indoor Temp"' in t.get("rawQueryText", "") for t in p.get("targets", []))
    ]
    assert len(indoor) == 1
    matches = [
        o
        for o in indoor[0]["fieldConfig"]["overrides"]
        if o["matcher"] == {"id": "byName", "options": "Indoor Temp"}
    ]
    assert any({"id": "custom.spanNulls", "value": False} in o["properties"] for o in matches)
