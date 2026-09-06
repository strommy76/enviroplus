"""
--------------------------------------------------------------------------------
FILE:        test_raw_retention.py
PATH:        ~/projects/enviroplus/tests/test_raw_retention.py
DESCRIPTION: Tests for the canonical raw-retention tier and the fail-loud write
             path it depends on.

CHANGELOG:
2026-08-06 15:47      Claude     [Feature] Initial implementation.
--------------------------------------------------------------------------------
"""

import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/pistrommy/projects")

from shared import raw_retention as rr
from shared.db_service import connect, write_row


@pytest.fixture()
def raw_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path))
    # Module-level dedup cache must not leak across tests.
    monkeypatch.setattr(rr, "_LAST_SHA", {})
    return tmp_path


def _records(root: Path, provider: str):
    files = list((root / provider).glob("*.ndjson"))
    assert len(files) == 1, f"expected one day file, got {files}"
    return [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()]


# ── Bytes are stored exactly as received ──────────────────────────────────────

def test_payload_round_trips_byte_identical(raw_root):
    """The canonical tier must return exactly what the provider sent."""
    payload = b'{"b":2,"a":1,  "ws":  true}\n'  # key order + whitespace preserved
    rr.retain("acme", payload, url="https://x.test/v1?apiKey=SECRET")

    day = next(iter((raw_root / "acme").glob("*.ndjson"))).stem
    recovered = [blob for _, _, blob in rr.read_day("acme", day) if blob is not None]
    assert recovered == [payload]


def test_integrity_failure_is_loud(raw_root):
    """A tampered payload must raise, not return silently wrong bytes."""
    rr.retain("acme", b'{"v":1}')
    f = next(iter((raw_root / "acme").glob("*.ndjson")))
    rec = json.loads(f.read_text().strip())
    rec["payload_b64"] = base64.b64encode(b'{"v":999}').decode("ascii")
    f.write_text(json.dumps(rec) + "\n")

    with pytest.raises(ValueError, match="integrity failure"):
        list(rr.read_day("acme", f.stem))


# ── A collection attempt is itself a fact ─────────────────────────────────────

def test_failed_pull_records_outcome_and_no_payload(raw_root):
    """A failed pull leaves a record of the failure, not an empty observation."""
    rr.record_outcome("acme", rr.OUTCOME_FETCH_ERROR, detail="timeout",
                      url="https://x.test/v1?api_key=SECRET")

    (rec,) = _records(raw_root, "acme")
    assert rec["outcome"] == rr.OUTCOME_FETCH_ERROR
    assert rec["detail"] == "timeout"
    assert "payload_b64" not in rec
    # The attempt is still enumerable by a replay consumer.
    day = next(iter((raw_root / "acme").glob("*.ndjson"))).stem
    assert [(o, b) for _, o, b in rr.read_day("acme", day)] == [
        (rr.OUTCOME_FETCH_ERROR, None)
    ]


def test_partial_outcome_is_distinguishable_from_absent_value(raw_root):
    """Sensor-dropout must be a recorded fact, not inferred from nulls."""
    rr.record_outcome("acme", rr.OUTCOME_PARTIAL, detail="outdoor array absent")
    (rec,) = _records(raw_root, "acme")
    assert rec["outcome"] == rr.OUTCOME_PARTIAL
    assert rec["detail"] == "outdoor array absent"


# ── Dedup is recorded, never silent ───────────────────────────────────────────

def test_consecutive_identical_payload_is_recorded_not_restored(raw_root):
    payload = b'{"same":1}'
    assert rr.retain("acme", payload) == rr.OUTCOME_OK
    assert rr.retain("acme", payload) == rr.OUTCOME_DUPLICATE

    recs = _records(raw_root, "acme")
    assert [r["outcome"] for r in recs] == [rr.OUTCOME_OK, rr.OUTCOME_DUPLICATE]
    assert "payload_b64" in recs[0] and "payload_b64" not in recs[1]
    # The skip is auditable: the digest is still recorded.
    assert recs[1]["sha256"] == recs[0]["sha256"]


def test_changed_payload_after_duplicate_is_stored(raw_root):
    rr.retain("acme", b'{"v":1}')
    rr.retain("acme", b'{"v":1}')
    rr.retain("acme", b'{"v":2}')
    day = next(iter((raw_root / "acme").glob("*.ndjson"))).stem
    blobs = [b for _, _, b in rr.read_day("acme", day) if b is not None]
    assert blobs == [b'{"v":1}', b'{"v":2}']


# ── Credentials never reach the canonical store ───────────────────────────────

@pytest.mark.parametrize("url", [
    "https://x.test/v1?apiKey=SUPERSECRET&lat=28",
    "https://x.test/v1?API_KEY=SUPERSECRET",
    "https://x.test/v1?api%5Fkey=SUPERSECRET",      # URL-encoded name
    "https://x.test/v1?a=1;token=SUPERSECRET",      # semicolon separator
    "https://x.test/v1#token=SUPERSECRET",          # fragment
    "https://x.test/v1?weird_param_name=SUPERSECRET",
])
def test_no_query_or_fragment_reaches_the_store(raw_root, url):
    """Dropping the query removes the whole leak class, not just known names."""
    rr.retain("acme", b"{}", url=url)
    body = next(iter((raw_root / "acme").glob("*.ndjson"))).read_text()
    assert "SUPERSECRET" not in body
    assert "x.test/v1" in body, "endpoint identity must survive"


def test_redact_keeps_endpoint_identity():
    assert rr.redact("https://x/v1/obs?k=S#f=S") == "https://x/v1/obs"


# ── Credentials inside the payload BODY are scrubbed, with lineage ────────────

def test_body_credential_is_scrubbed_from_stored_payload(raw_root):
    """A device secret in the response body must not reach the canonical store."""
    payload = (b'[{"passkey":"ABCDEF0123456789ABCDEF0123456789",'
               b'"tempf":81.3,"humidity":64}]')
    rr.retain("acme", payload)

    body = next(iter((raw_root / "acme").glob("*.ndjson"))).read_text()
    assert "ABCDEF0123456789ABCDEF0123456789" not in body
    assert "ABCDEF0123456789ABCDEF0123456789" not in base64.b64decode(
        json.loads(body)["payload_b64"]).decode()


def test_scrub_preserves_every_other_byte(raw_root):
    """Only the secret's bytes change -- key order and whitespace survive."""
    payload = b'[{"passkey":"S3CR3T","b":2,  "a":1,"ws":  true}]'
    rr.retain("acme", payload)
    day = next(iter((raw_root / "acme").glob("*.ndjson"))).stem
    (blob,) = [b for _, _, b in rr.read_day("acme", day) if b is not None]
    assert blob == b'[{"passkey":"<redacted>","b":2,  "a":1,"ws":  true}]'


def test_scrub_records_lineage(raw_root):
    """What arrived stays provable even though the secret is not retained."""
    payload = b'[{"passkey":"S3CR3T","tempf":81.3}]'
    expected = hashlib.sha256(payload).hexdigest()
    rr.retain("acme", payload)

    (rec,) = _records(raw_root, "acme")
    assert rec["scrubbed_keys"] == ["passkey"]
    assert rec["sha256_as_received"] == expected
    assert rec["sha256"] != expected  # stored bytes differ from what arrived


def test_payload_without_secrets_records_no_scrub_lineage(raw_root):
    rr.retain("acme", b'{"tempf":81.3}')
    (rec,) = _records(raw_root, "acme")
    assert "scrubbed_keys" not in rec and "sha256_as_received" not in rec


# ── A provider key must not escape the retention root ─────────────────────────

@pytest.mark.parametrize("bad", [
    "../evil", "nws/../../evil", "/etc/evil", "nws/../..", "..", "nws/ev il",
])
def test_unsafe_provider_key_is_refused(raw_root, bad):
    with pytest.raises(ValueError):
        rr.retain(bad, b"{}")


def test_hierarchical_provider_key_is_allowed(raw_root):
    """Legitimate per-station keys must still work."""
    rr.retain("nws/KCOF", b'{"v":1}')
    assert (raw_root / "nws" / "KCOF").is_dir()


# ── Dedup is O(1) and survives the day boundary ───────────────────────────────

def test_dedup_does_not_rescan_the_day_file(raw_root, monkeypatch):
    """The dedup check must not re-read the whole day -- that was quadratic."""
    calls = []
    real = rr._tail_sha
    monkeypatch.setattr(rr, "_tail_sha", lambda p: (calls.append(p), real(p))[1])
    for i in range(5):
        rr.retain("acme", f'{{"v":{i}}}'.encode())
    assert len(calls) <= 1, f"day file re-read {len(calls)} times"


def test_repeat_within_the_same_day_is_a_duplicate(raw_root):
    """Within one day, a byte-identical payload is recorded but not re-stored.

    Renamed: this previously claimed to test cross-midnight behaviour while
    both writes landed in the same day file, and asserted the opposite of the
    design (day files are self-contained -- see the boundary test below).
    """
    payload = b'{"v":1}'
    assert rr.retain("acme", payload) == rr.OUTCOME_OK
    assert rr.retain("acme", payload) == rr.OUTCOME_DUPLICATE


# ── Crash safety: a record is durable the moment it is written ────────────────

def test_record_is_flushed_immediately(raw_root):
    """No buffering window in which bytes exist without their integrity record."""
    rr.retain("acme", b'{"v":1}')
    recs = _records(raw_root, "acme")  # read from a separate handle, no close()
    assert len(recs) == 1 and recs[0]["sha256"]


# ── write_row must fail loud on non-integrity errors ──────────────────────────

def test_write_row_raises_on_operational_error(tmp_path):
    """A lock/operational failure must not look like an ignored duplicate."""
    db = connect(str(tmp_path / "t.db"))
    db.execute("CREATE TABLE t (ts TEXT PRIMARY KEY, v REAL)")
    with pytest.raises(sqlite3.Error):
        write_row(db, "no_such_table", {"ts": "x", "v": 1.0})


def test_write_row_returns_false_only_for_ignored_duplicate(tmp_path):
    db = connect(str(tmp_path / "t.db"))
    db.execute("CREATE TABLE t (ts TEXT PRIMARY KEY, v REAL)")
    assert write_row(db, "t", {"ts": "a", "v": 1.0}, or_ignore=True) is True
    assert write_row(db, "t", {"ts": "a", "v": 2.0}, or_ignore=True) is False
    # The suppressed write must not have altered the stored row.
    assert db.execute("SELECT v FROM t WHERE ts='a'").fetchone()[0] == 1.0


def test_busy_timeout_is_set(tmp_path):
    db = connect(str(tmp_path / "t.db"))
    from shared.db_service import BUSY_TIMEOUT_MS
    assert db.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS


# ── Operational write failure degrades observably; it must not propagate ──────

def test_os_write_failure_is_logged_not_raised(raw_root, monkeypatch, caplog):
    """A full or unwritable disk must not take the collector loop down with it.

    These calls sit inside the collectors' exception handlers, so a raise would
    exit the while loop and lose the derived write too -- both tiers instead of
    one.
    """
    import logging

    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(rr.Path, "open", boom)
    with caplog.at_level(logging.ERROR):
        rr.record_outcome("acme", rr.OUTCOME_FETCH_ERROR, detail="x")
        assert rr.retain("acme", b'{"v":1}') == rr.OUTCOME_OK
    assert "retention write failed" in caplog.text


def test_programming_error_still_raises(raw_root):
    """An unsafe provider key is a deterministic bug and must stay loud."""
    with pytest.raises(ValueError):
        rr.record_outcome("../evil", rr.OUTCOME_FETCH_ERROR)


# ── Day files stay self-contained ─────────────────────────────────────────────

def test_dedup_does_not_span_the_day_boundary(raw_root):
    """A duplicate must never reference a payload stored in another day file.

    Otherwise replaying a single restored day is silently incomplete, and
    pruning an old day severs the chain.
    """
    payload = b'{"v":1}'
    rr.retain("acme", payload)
    # Same payload, next day: the cache is day-scoped, so it must re-store.
    today = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).date().isoformat()
    root = str(raw_root)
    assert (root, "acme", "2026-01-01") not in rr._LAST_SHA
    assert [k[2] for k in rr._LAST_SHA if k[0] == root] == [today]


def test_every_day_file_is_independently_replayable(raw_root):
    """Every stored payload is recoverable from its own day file alone."""
    for v in (1, 1, 2):
        rr.retain("acme", f'{{"v":{v}}}'.encode())
    day = next(iter((raw_root / "acme").glob("*.ndjson"))).stem
    recs = list(rr.read_day("acme", day))
    # Duplicates carry no payload, but every distinct payload is present here.
    assert [b for _, _, b in recs if b] == [b'{"v":1}', b'{"v":2}']


# ── The read path honours the same boundary as the write path ─────────────────

@pytest.mark.parametrize("bad", ["../evil", "/etc/evil", "nws/../.."])
def test_read_day_refuses_unsafe_provider_key(raw_root, bad):
    with pytest.raises(ValueError):
        list(rr.read_day(bad, "2026-08-06"))


# ── The tail window must exceed the largest real record ───────────────────────

def test_tail_window_exceeds_largest_measured_record(raw_root):
    """A tail read must never land mid-line and silently disable dedup."""
    big = b'{"pad":"' + b"x" * (200 * 1024) + b'"}'
    rr.retain("acme", big)
    rr._LAST_SHA.clear()                      # force the file path, not the cache
    assert rr.retain("acme", big) == rr.OUTCOME_DUPLICATE


# ── The canonical root is never guessed ───────────────────────────────────────

def test_unconfigured_write_is_refused(monkeypatch):
    """Writing to canonical must not be the default for any importer.

    An earlier version fell back to the production path when unset, so review
    tooling and ad-hoc scripts silently appended non-authoritative records to
    the live store -- twice, the second time after the first was cleaned up.
    """
    monkeypatch.delenv("ENVIRO_RAW_ROOT", raising=False)
    monkeypatch.setattr(rr, "_ROOT", None)
    with pytest.raises(rr.RetentionNotConfiguredError):
        rr.retain("acme", b"{}")
    with pytest.raises(rr.RetentionNotConfiguredError):
        rr.record_outcome("acme", rr.OUTCOME_FETCH_ERROR)


def test_configure_declares_the_root(tmp_path, monkeypatch):
    monkeypatch.delenv("ENVIRO_RAW_ROOT", raising=False)
    monkeypatch.setattr(rr, "_ROOT", None)
    monkeypatch.setattr(rr, "_LAST_SHA", {})
    rr.configure(tmp_path)
    rr.retain("acme", b'{"v":1}')
    assert list((tmp_path / "acme").glob("*.ndjson"))


def test_dedup_state_does_not_leak_across_roots(tmp_path, monkeypatch):
    """A root change starts with no dedup memory: the first arrival into the new
    root is stored, never labelled duplicate against the previous root."""
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path / "root-a"))
    assert rr.retain("acme", b'[{"v": 1}]') == rr.OUTCOME_OK
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path / "root-b"))
    assert rr.retain("acme", b'[{"v": 1}]') == rr.OUTCOME_OK
    day = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    assert [o for _, o, _ in rr.read_day("acme", day)] == [rr.OUTCOME_OK]
