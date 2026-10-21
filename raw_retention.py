"""
--------------------------------------------------------------------------------
FILE:        raw_retention.py
PATH:        ~/projects/enviroplus/raw_retention.py
DESCRIPTION: Canonical (Tier 1) retention of provider responses and local
             sensor reads as received, plus a record of every collection
             attempt including the ones that returned nothing.

             Tier: CANONICAL. The derived SQLite tables are projections of this
             store and are rebuildable from it by replay. Payloads are stored as
             received with exactly one exception: credential values carried in a
             response body are scrubbed, because a device secret is not a fact
             about the weather and has no reconstruction value. That scrub is
             recorded per record (scrubbed_keys + sha256_as_received), so what
             arrived stays provable. Nothing else is parsed or interpreted here.

             A collection attempt is itself a fact. A failed pull records an
             outcome rather than a row of nulls, so "the sensor was offline"
             and "this value was absent" stop being the same observation.

             Layout: raw-capture/<provider>/<YYYY-MM-DD>.ndjson, one line per
             attempt, appended and flushed immediately so an interrupted
             process never leaves bytes without their integrity record. Day
             files are self-contained: dedup never spans a day boundary.

             `bytes` is the length of what is STORED. When a scrub occurred,
             sha256_as_received identifies what arrived.

CHANGELOG:
2026-10-20 23:35      Claude      [Refactor] Moved here from ~/projects/shared:
                                      every consumer is in enviroplus, so it is
                                      project code (operator, 2026-10-20 23:23).
2026-10-20 23:15      Claude     [Fix] A failed append raises
                                      RetentionWriteError instead of being
                                      logged while retain() reported the
                                      arrival as stored. Callers then wrote
                                      derived rows the canonical tier did not
                                      hold, and the failure read as success. A
                                      partially written line is truncated away
                                      first, so the day file stays readable.
                                      Adds days(provider).
2026-08-06 15:54      Claude     [Fix] Scrub body credentials with recorded
                                      lineage; refuse unsafe provider keys on
                                      both read and write paths; make OS-level
                                      write failure degrade observably instead
                                      of propagating into collector loops; scope
                                      the dedup cache per day so day files stay
                                      self-contained; size the tail window above
                                      the largest measured record.
2026-08-06 15:35      Claude     [Feature] Initial implementation -- retain(),
                                      record_outcome(), read_day().
--------------------------------------------------------------------------------
"""

import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class RetentionNotConfiguredError(RuntimeError):
    """The canonical root was never declared. Writing is refused rather than guessed."""


class RetentionWriteError(OSError):
    """A record could not be durably appended; the canonical tier does not hold
    it. Whatever the caller would derive from it has no source."""


class OutcomeAlreadyRecorded(Exception):
    """Raised by a fetch path that has already recorded this attempt's outcome.

    Without it, a caller whose exception handler also records would write a
    SECOND record for one attempt, under a different and wrong cause: a payload
    that arrived and was stored would be labelled "never arrived".
    """

# Credential-bearing keys carried inside a payload BODY. A device secret is not
# a fact about the weather: it has no reconstruction value and is pure liability
# in a store that gets backed up. Doctrine's repair for an artifact that cannot
# safely cross a boundary is to scrub it and record that the scrub happened --
# so only the secret's own bytes are replaced and every other byte, including
# key order and whitespace, survives untouched. Both digests are recorded, so
# the original payload remains provable even though it is not retained.
_SECRET_BODY_KEYS = re.compile(
    rb'("(?:passkey|api[_-]?key|apikey|app(?:lication)?[_-]?key|token|secret)"'
    rb'\s*:\s*")([^"]*)(")',
    re.IGNORECASE,
)

REDACTED = b"<redacted>"

# A provider key becomes a directory path, so it must not be able to escape the
# retention root or address anything outside it.
_SAFE_KEY_PART = re.compile(r"^[A-Za-z0-9._-]+$")

# Outcomes are causes, not severities. A failure to write the derived row is not
# a failure to fetch, and recording it as one would make the canonical store lie
# about which subsystem broke.
OUTCOME_OK = "ok"
OUTCOME_DUPLICATE = "duplicate"        # byte-identical to the previous payload
OUTCOME_EMPTY = "empty"                # arrived, carried no observation
OUTCOME_MALFORMED = "malformed"        # arrived, could not be parsed
OUTCOME_PARTIAL = "partial"            # arrived, a sensor group was absent
OUTCOME_FETCH_ERROR = "fetch_error"    # never arrived
OUTCOME_WRITE_ERROR = "write_error"    # arrived and stored; derived write failed


# The canonical root is declared, never inferred. A default that decides where
# truth is written is an ambient default: it makes writing to the canonical tier
# the behaviour of any process that merely imports this module, which inverts a
# tier required to default-deny non-authoritative writes.
_ROOT: Path | None = None


def configure(root: str | Path) -> None:
    """Declare the retention root. Required before any write."""
    global _ROOT
    _ROOT = Path(root)


def _root() -> Path:
    env = os.environ.get("ENVIRO_RAW_ROOT")
    if env:
        return Path(env)
    if _ROOT is None:
        raise RetentionNotConfiguredError(
            "raw retention root is not configured; call raw_retention.configure(path) "
            "or set ENVIRO_RAW_ROOT. Refusing to guess the canonical store."
        )
    return _ROOT


def redact(url: str | None) -> str | None:
    """Reduce a URL to scheme, host and path -- the query is dropped entirely.

    Matching secrets by parameter name is a heuristic over an open set, so every
    new provider is a new opportunity to miss one. Dropping the query removes the
    defect class instead of guarding its known instances, at no cost: the query is
    reconstructible from configuration, and the record needs endpoint identity.
    """
    if not url:
        return url
    return url.split("?", 1)[0].split("#", 1)[0]


def scrub_body(raw: bytes) -> tuple[bytes, list[str]]:
    """Replace credential values inside a payload, leaving all other bytes intact.

    Returns (scrubbed_bytes, names_of_scrubbed_keys).
    """
    found: list[str] = []

    def _sub(m):
        name = m.group(1).decode("utf-8", "replace").strip('":').strip()
        found.append(name)
        return m.group(1) + REDACTED + m.group(3)

    return _SECRET_BODY_KEYS.sub(_sub, raw), found


def _safe_provider_dir(provider: str) -> Path:
    """Resolve a provider key to a directory, refusing anything that escapes root.

    The key may be hierarchical (``nws/KCOF``), but each part must be an ordinary
    name -- no traversal, no absolute paths, no separators smuggled through.
    """
    # Every segment must be present and ordinary. Empty segments are not skipped:
    # an absolute-looking key ("/etc/x") or a doubled separator would otherwise be
    # silently rebased inside the root rather than refused.
    parts = provider.split("/")
    if not parts or not all(_SAFE_KEY_PART.match(p) for p in parts):
        raise ValueError(f"unsafe provider key for retention path: {provider!r}")
    root = _root().resolve()
    target = (root.joinpath(*parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"provider key escapes retention root: {provider!r}")
    return target


def _day_file(provider: str, when: datetime) -> Path:
    d = _safe_provider_dir(provider)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{when.date().isoformat()}.ndjson"


def _append(provider: str, record: dict, when: datetime) -> None:
    """Append one record and flush it to disk, or raise RetentionWriteError.

    Success means the record is durably stored; nothing else does. A failure
    is raised so the caller cannot go on to derive from a record that is not
    there: a derived row with no canonical source cannot be rebuilt, and a
    logged-only failure reads as success. Bytes a failed write left in the
    file (a short write, or a write that reached the file before fsync
    failed) are truncated away, so the day file stays readable for replay.
    Unbuffered descriptor I/O, so the truncate cannot itself need a flush.

    An unsafe provider key is a programming fault and raises ValueError.
    """
    _safe_provider_dir(provider)          # ValueError for an unsafe key
    data = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        fd = os.open(_day_file(provider, when), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o666)
        try:
            start = os.fstat(fd).st_size
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            except OSError:
                os.ftruncate(fd, start)
                raise
        finally:
            os.close(fd)
    except OSError as exc:
        raise RetentionWriteError(
            f"raw retention write failed for {provider}: {exc}") from exc


# Digest of the last payload retained, so the dedup check is O(1) per call rather
# than re-reading the day file -- re-reading was quadratic across a day, parsing
# ~1M records by evening for a 60 s poller.
#
# Keyed by (provider, day) so day files stay self-contained. A digest carried
# across a day boundary lets a file open with a duplicate whose payload lives
# elsewhere, making single-day replay silently incomplete and pruning
# destructive, and makes the stored shape depend on process uptime.
# Keyed by (root, provider, day): dedup state belongs to the store it was read
# from. Keyed without the root, a root change (configure(), ENVIRO_RAW_ROOT)
# would carry a stale digest across and label a fresh arrival in the new root
# `duplicate` without storing its bytes.
_LAST_SHA: dict[tuple[str, str, str], str] = {}

# Must exceed the largest single record, or a tail read lands mid-line and
# silently disables dedup. Sized from the measured worst-case payload with an
# order of magnitude of margin; read once per provider per process.
_TAIL_WINDOW_BYTES = 4 * 1024 * 1024


def _tail_sha(path: Path) -> str | None:
    """Digest from the last record of a day file, read from the end."""
    if not path.exists():
        return None
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        window = min(size, _TAIL_WINDOW_BYTES)
        fh.seek(size - window)
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("sha256"):
            return rec["sha256"]
    return None


def _last_sha(provider: str, when: datetime) -> str | None:
    """SHA-256 of the most recent retained payload in THIS day, for dedup."""
    key = (str(_root().resolve()), provider, when.date().isoformat())
    cached = _LAST_SHA.get(key)
    if cached is not None:
        return cached
    found = _tail_sha(_day_file(provider, when))
    if found:
        _LAST_SHA[key] = found
    return found


def retain(provider: str, raw: bytes, *, url: str | None = None,
           outcome: str = OUTCOME_OK, detail: str | None = None) -> str:
    """Store a provider response verbatim and record its arrival.

    Consecutive byte-identical payloads are recorded but not re-stored: for
    these APIs an identical body carries no new observation, and the skip is
    itself logged so the record remains a complete account of every attempt.

    Returns the outcome recorded once it is durably stored; raises
    RetentionWriteError when it could not be.
    """
    now = datetime.now(timezone.utc)
    original_digest = hashlib.sha256(raw).hexdigest()
    stored, scrubbed_keys = scrub_body(raw)
    digest = hashlib.sha256(stored).hexdigest()

    try:
        previous = _last_sha(provider, now)
    except OSError as exc:
        # Creating or reading the day file failed: the record cannot be stored.
        raise RetentionWriteError(
            f"raw retention write failed for {provider}: {exc}") from exc
    if digest == previous:
        _append(provider, {
            "captured_utc": now.isoformat(),
            "outcome": OUTCOME_DUPLICATE,
            "sha256": digest,
            "bytes": len(stored),
            "url": redact(url),
        }, now)
        return OUTCOME_DUPLICATE

    record = {
        "captured_utc": now.isoformat(),
        "outcome": outcome,
        "sha256": digest,
        "bytes": len(stored),
        "url": redact(url),
        "detail": detail,
        "payload_b64": base64.b64encode(stored).decode("ascii"),
    }
    if scrubbed_keys:
        # Lineage: what arrived is still provable, even though the secret in it
        # is not retained.
        record["scrubbed_keys"] = sorted(set(scrubbed_keys))
        record["sha256_as_received"] = original_digest
    _append(provider, record, now)
    _LAST_SHA[(str(_root().resolve()), provider, now.date().isoformat())] = digest
    return outcome


def record_outcome(provider: str, outcome: str, *, detail: str | None = None,
                   url: str | None = None) -> None:
    """Record a collection attempt that produced no payload.

    This is the fact that replaces an empty row: the attempt happened, it
    failed, and the record says so. Raises RetentionWriteError when the record
    could not be stored.
    """
    now = datetime.now(timezone.utc)
    _append(provider, {
        "captured_utc": now.isoformat(),
        "outcome": outcome,
        "detail": detail,
        "url": redact(url),
    }, now)


def days(provider: str) -> list[str]:
    """The UTC days (YYYY-MM-DD) that have a day file for `provider`, oldest
    first. Replay consumers use it to find where retention begins."""
    d = _safe_provider_dir(provider)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.ndjson"))


def read_day(provider: str, day: str):
    """Yield (captured_utc, outcome, payload_bytes_or_None) for one day.

    payload is None for duplicate and no-payload records. Replay consumers
    reconstruct derived rows from this; it is the recovery path that makes the
    SQLite tables rebuildable.
    """
    path = _safe_provider_dir(provider) / f"{day}.ndjson"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                log.error("corrupt retention record in %s: %s", path, exc)
                raise
            payload = rec.get("payload_b64")
            if payload is not None:
                blob = base64.b64decode(payload)
                if hashlib.sha256(blob).hexdigest() != rec.get("sha256"):
                    raise ValueError(
                        f"retention integrity failure in {path}: sha256 mismatch "
                        f"at {rec.get('captured_utc')}"
                    )
                yield rec["captured_utc"], rec.get("outcome"), blob
            else:
                yield rec["captured_utc"], rec.get("outcome"), None
