"""Generate the provider-health timer from its single cadence policy."""

import json
from pathlib import Path

from shared.systemd_units import render_unit


def rendered_units(root):
    policy = json.loads((root / "config/provider_health.json").read_text())
    return {
        "enviro_provider_health.service": (
            root / "config/unit_templates/enviro_provider_health.service.in"
        ).read_text(),
        "enviro_provider_health.timer": render_unit(
            (root / "config/unit_templates/enviro_provider_health.timer.in").read_text(),
            {"Timer": {"OnUnitActiveSec": [str(policy["check_interval_seconds"])]}},
        ),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    for name, content in rendered_units(root).items():
        (root / name).write_text(content)
