"""All current native units use rendering-process and config-root bindings."""

import shlex
import shutil
import sys
from configparser import ConfigParser
from pathlib import Path

from service_units import rendered_units


def test_all_units_derive_interpreter_and_root(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "relocated project"
    shutil.copytree(source / "config", root / "config")
    for template in source.glob("*.in"):
        shutil.copy(template, root)
    interpreter = str(tmp_path / "other environment/bin/python")
    monkeypatch.setattr(sys, "executable", interpreter)
    units = rendered_units(root)
    assert {path.stem for path in (root / "config/unit_templates").glob("*.in")} < units.keys()
    for name, content in units.items():
        unit = ConfigParser(interpolation=None)
        unit.read_string(content)
        if name.endswith(".service"):
            assert shlex.split(unit["Service"]["ExecStart"])[0] == interpreter, name
            assert Path(unit["Service"]["WorkingDirectory"]) == root, name
            if "Environment" in unit["Service"]:
                for binding in shlex.split(unit["Service"]["Environment"]):
                    if binding.startswith("PYTHONPATH="):
                        assert all(
                            Path(value).resolve() in (root, root.parent)
                            for value in binding.partition("=")[2].split(":")
                        )
        if "Documentation" in unit["Unit"]:
            assert unit["Unit"]["Documentation"] == f"file://{root}/config/backup.json"
