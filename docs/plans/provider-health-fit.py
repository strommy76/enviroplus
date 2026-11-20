"""One-use read-only fit from all retained current-day Ambient outdoor returns."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from shared.config_service import load_env, require

from ambient_wx import classify_response
from raw_retention import configure, read_day

load_env("/home/pistrommy/projects/enviroplus/.env")
parser = argparse.ArgumentParser()
parser.add_argument("raw_root", type=Path)
parser.add_argument(
    "--through", required=True, help="Immutable last captured_utc included in this fit"
)
args = parser.parse_args()
configure(args.raw_root)
day = args.through[:10]
ages = []
observation = None
last_capture = None
first_observed = None
new_ages = []
new_times = []
previous_observed = None
for captured, outcome, blob in read_day("ambient", day):
    if captured > args.through:
        break
    if blob is not None:
        observation, classified, _ = classify_response(blob, require("AW_MAC"))
        if classified != "ok":
            observation = None
    if observation is not None and outcome in ("ok", "duplicate"):
        observed = datetime.fromtimestamp(observation["dateutc"] / 1000, timezone.utc)
        age = (datetime.fromisoformat(captured) - observed).total_seconds()
        ages.append(age)
        if first_observed is None:
            first_observed = observed
        elif observed != previous_observed:
            new_ages.append(age)
            new_times.append(observed)
        previous_observed = observed
        last_capture = captured
if not ages:
    raise RuntimeError("No retained successful outdoor arrivals to fit")
print(
    json.dumps(
        {
            "day": day,
            "last_capture": last_capture,
            "observations": len(ages),
            "max_age_seconds": max(ages),
            "min_age_seconds": min(ages),
            "first_observed": first_observed.isoformat(),
            "new_observations": len(new_ages),
            "max_new_arrival_age_seconds": max(new_ages),
            "max_new_observation_step_seconds": max(
                (b - a).total_seconds() for a, b in zip(new_times, new_times[1:])
            ),
        },
        indent=2,
    )
)
