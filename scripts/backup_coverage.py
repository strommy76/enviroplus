"""Declare Enviro-owned paths and report their actual backup observations."""

import argparse
import json
from pathlib import Path

from backup_snapshots import snapshot_stamp
from scripts.backup_enviro import DEFAULT_CONFIG, load_config


def coverage(config_path: Path) -> dict:
    cfg = load_config(config_path)
    # Resolve ownership before reading evidence. A broken/missing observation
    # never authorizes the host lane to copy the owner's live stores instead.
    result = {
        "exclusions": [source["source_path"] for source in cfg["sources"].values()],
        "gaps": [],
        "restore_owners": [str(Path(__file__).with_name("backup_enviro.py"))],
    }
    manifests = sorted(Path(cfg["manifest"]["manifest_dir"]).glob("backup_*.json"))
    try:
        latest = json.loads(manifests[-1].read_text()) if manifests else None
    except (OSError, ValueError) as exc:
        result["gaps"].append(
            {"path": str(manifests[-1]), "stage": "enviro_backup", "cause": str(exc)}
        )
        return result
    remote = cfg["remote"]
    base = f"{remote['rclone_remote_name']}:{remote['rclone_remote_path'].strip('/')}"
    for name, source in cfg["sources"].items():
        destination = base + "/" + source["remote_subpath"].strip("/")
        matches = []
        for row in latest["results"] if latest else []:
            if row["verified"] is not True or row["detail"].get("error"):
                continue
            if source["kind"] == "tree":
                matched = (
                    row["kind"] == "tree"
                    and row["source"] == source["source_path"]
                    and row["remote_object"] == destination
                )
            else:
                staged = Path(row["source"])
                matched = (
                    row["kind"] == "file"
                    and row["detail"].get("source_path") == source["source_path"]
                    and staged.parent == Path(cfg["local_staging"]["staging_dir"])
                    and snapshot_stamp(staged.name, Path(source["source_path"]).stem) is not None
                    and row["remote_object"] == destination + "/" + staged.name
                    and row["local_hash"] is not None
                    and row["local_hash"] == row["remote_hash"]
                )
            if matched:
                matches.append(row)
        if len(matches) != 1:
            result["gaps"].append(
                {
                    "path": source["source_path"],
                    "stage": "enviro_backup",
                    "target": name,
                    "cause": "Latest backup lacks unique verified source evidence",
                    "last_verified": None,
                }
            )
    result["enviro_proof"] = str(manifests[-1]) if manifests else None
    result["enviro_cutoff"] = latest["generated_utc"] if latest else None
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result = coverage(parser.parse_args().config)
    print(json.dumps(result))
    raise SystemExit(bool(result["gaps"]))
