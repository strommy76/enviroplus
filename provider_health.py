"""Read-only freshness of configured provider observations, independently checked."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from shared.config_service import load_env, require

from ambient_wx import outdoor_presence_sql


def check(database, policy, now):
    results = []
    # A broken query/observation belongs to its lane, not its siblings.
    for lane in policy["lanes"]:
        result = {"lane": lane["name"], "problem": None}
        try:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                row = db.execute(
                    lane["query"].format(outdoor_presence=outdoor_presence_sql())
                ).fetchone()
            if row is None or row["ts"] is None:
                result["problem"] = "observation_missing"
            else:
                observed = datetime.fromisoformat(row["ts"])
                if observed.tzinfo is None:
                    zone = ZoneInfo(lane["timezone"])
                    # AirNow states EST/EDT; match the actual abbreviation,
                    # including the two occurrences of the autumn clock hour.
                    candidates = [observed.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
                    observed = next(
                        value
                        for value in candidates
                        if "timezone_abbreviation" not in row.keys()
                        or value.tzname() == row["timezone_abbreviation"]
                    )
                age = (now - observed).total_seconds()
                result.update(observed_at=observed.isoformat(), age_seconds=age)
                if age < 0:
                    result["problem"] = "observation_in_future"
                elif age > lane["max_age_seconds"]:
                    result["problem"] = "observation_stale"
        except (sqlite3.Error, OSError, ValueError, StopIteration) as error:
            result.update(
                problem="observation_unreadable", detail=f"{type(error).__name__}: {error}"
            )
        results.append(result)
    return results


def main():
    root = Path(__file__).resolve().parent
    load_env(str(root / ".env"), expect_key="SQLITE_PATH")
    policy = json.loads((root / "config/provider_health.json").read_text())
    results = check(require("SQLITE_PATH"), policy, datetime.now(timezone.utc))
    print(json.dumps(results, indent=2))
    return int(any(result["problem"] is not None for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
