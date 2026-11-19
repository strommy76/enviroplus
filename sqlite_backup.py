"""Consistent SQLite capture and artifact-bound restore validation."""

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.backup_configuration import load_configuration
from shared.backup_estimates import fractional_tree_estimate, fractional_upload_bytes
from shared.backup_records import write_record
from shared.config_service import load_env, require


def database_facts(path: Path) -> dict:
    """Read this artifact, never a later live store, as the restore oracle."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        status = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {status}")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        counts = {
            name: connection.execute(
                'SELECT count(*) FROM "' + name.replace('"', '""') + '"'
            ).fetchone()[0]
            for name in tables
        }
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest, "table_rows": counts}


def capture(source: Path, output_dir: Path) -> dict:
    """Use SQLite's existing VACUUM INTO seam, then validate once for evidence."""
    target = output_dir / "snapshot.db"
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as connection:
        connection.execute("VACUUM INTO ?", (str(target),))
    evidence = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "artifact": target.name,
        "facts": database_facts(target),
    }
    write_record(output_dir / "capture.json", evidence)
    return evidence


def verify(directory: Path) -> dict:
    evidence = json.loads((directory / "capture.json").read_text())
    observed = database_facts(directory / evidence["artifact"])
    if observed != evidence["facts"]:
        raise RuntimeError("Restored SQLite artifact differs from its captured evidence")
    return evidence


def estimate(source: Path, settings: dict) -> dict:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as connection:
        size = (
            connection.execute("PRAGMA page_count").fetchone()[0]
            * connection.execute("PRAGMA page_size").fetchone()[0]
        )
    staging = size + settings["capture_evidence_bytes"]
    return {
        "staging_bytes": staging,
        "upload_bytes": fractional_upload_bytes(staging, settings["native_overhead_fraction"]),
        "source_bytes": size,
        "source_files": 2,
        "derivation": "Current allocated SQLite pages plus measured capture evidence and provisional native encoding fraction; no compression credit",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_subparsers(dest="mode", required=True)
    capture_parser = mode.add_parser("capture")
    capture_parser.add_argument("--config", type=Path, required=True)
    capture_parser.add_argument("--component", required=True)
    capture_parser.add_argument("--output-dir", type=Path, required=True)
    estimate_parser = mode.add_parser("estimate")
    estimate_parser.add_argument("--config", type=Path, required=True)
    estimate_parser.add_argument("--component", required=True)
    estimate_parser.add_argument("--output-dir", type=Path)
    restore_parser = mode.add_parser("verify")
    restore_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.mode == "verify":
        result = verify(args.directory)
    else:
        _, config, _ = load_configuration(args.config)
        component = config["components"][args.component]
        if config["environment_file"] is not None:
            load_env(config["environment_file"])
        if args.mode == "capture":
            result = capture(Path(require("SQLITE_PATH")), args.output_dir)
        elif args.output_dir is not None:
            result = fractional_tree_estimate(
                args.output_dir, component["estimate"]["native_overhead_fraction"]
            )
        else:
            result = estimate(Path(require("SQLITE_PATH")), component["estimate"])
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
