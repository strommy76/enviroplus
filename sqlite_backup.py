"""Consistent SQLite capture and artifact-bound restore validation."""

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.backup_records import write_record
from shared.config_service import require


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


def measure(source: Path) -> dict:
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as connection:
        size = (
            connection.execute("PRAGMA page_count").fetchone()[0]
            * connection.execute("PRAGMA page_size").fetchone()[0]
        )
    return {
        "source_bytes": size,
        "derivation": "Current allocated SQLite pages",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_subparsers(dest="mode", required=True)
    capture_parser = mode.add_parser("capture")
    capture_parser.add_argument("--config", type=Path, required=True)
    capture_parser.add_argument("--component", required=True)
    capture_parser.add_argument("--output-dir", type=Path, required=True)
    measure_parser = mode.add_parser("measure")
    measure_parser.add_argument("--config", type=Path, required=True)
    measure_parser.add_argument("--component", required=True)
    restore_parser = mode.add_parser("verify")
    restore_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.mode == "verify":
        result = verify(args.directory)
    else:
        source = Path(require("SQLITE_PATH"))
        if args.mode == "capture":
            result = capture(source, args.output_dir)
        else:
            result = measure(source)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
