"""Read-only freshness of configured provider observations, independently checked."""

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from shared.config_service import load_env, require

from ambient_wx import outdoor_presence_sql


def producer_state(unit):
    result = subprocess.run(
        ["systemctl", "show", unit, "--property=LoadState,UnitFileState"],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def load_policy(root):
    policy = json.loads((root / "config/provider_health.json").read_text())
    capture = json.loads(Path(require("CONFIG_PATH")).read_text())
    for lane in policy["lanes"]:
        if "producer_unit" in lane:
            # Provisional: interval-start age spans the closed and open publish
            # grids, plus check phase and display-loop delay. Settle loaded
            # healthy publication ages/sensor I/O when hardware is activated.
            lane["max_age_seconds"] = (
                2 * capture["intervals"]["publish_s"]
                + policy["check_interval_seconds"]
                + capture["intervals"]["display_refresh_s"]
            )
    return policy


def check(database, policy, now):
    results = []
    # A broken query/observation belongs to its lane, not its siblings.
    for lane in policy["lanes"]:
        result = {"lane": lane["name"], "problem": None}
        try:
            if "producer_unit" in lane:
                state = producer_state(lane["producer_unit"])
                if state.get("LoadState") == "not-found":
                    result.update(active=False, detail="producer not installed")
                    results.append(result)
                    continue
                if state.get("LoadState") == "loaded" and state.get("UnitFileState") == "disabled":
                    result.update(active=False, detail="producer disabled")
                    results.append(result)
                    continue
                if state.get("LoadState") != "loaded" or state.get("UnitFileState") != "enabled":
                    raise ValueError(f"unreadable producer state: {state}")
                result["active"] = True
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
        except (
            sqlite3.Error,
            OSError,
            ValueError,
            StopIteration,
            subprocess.CalledProcessError,
        ) as error:
            result.update(
                problem="observation_unreadable", detail=f"{type(error).__name__}: {error}"
            )
        results.append(result)
    return results


def main():
    root = Path(__file__).resolve().parent
    load_env(str(root / ".env"), expect_key="SQLITE_PATH")
    policy = load_policy(root)
    results = check(require("SQLITE_PATH"), policy, datetime.now(timezone.utc))
    print(json.dumps(results, indent=2))
    return int(any(result["problem"] is not None for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
