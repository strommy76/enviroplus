"""Derive Enviro native units through the shared renderer and backup owner."""

import json
from pathlib import Path

from shared.backup_units import rendered_units as backup_units
from shared.systemd_units import render_unit


def rendered_units(root):
    policy = json.loads((root / "config/provider_health.json").read_text())
    units = {
        template.stem: render_unit(template.read_text(), {}, root=root)
        for template in (root / "config/unit_templates").glob("*.in")
    }
    units["enviro_provider_health.timer"] = render_unit(
        units["enviro_provider_health.timer"],
        {"Timer": {"OnUnitActiveSec": [str(policy["check_interval_seconds"])]}},
    )
    units.update(backup_units(root / "config/backup.json"))
    return units


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    for name, content in rendered_units(root).items():
        (root / name).write_text(content)
