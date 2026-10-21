"""
--------------------------------------------------------------------------------
FILE:        test_raw_retention_write_failure.py
PATH:        ~/projects/enviroplus/tests/test_raw_retention_write_failure.py
DESCRIPTION: A record that could not be durably stored raises, never reports
             success, and leaves the day file readable.

CHANGELOG:
2026-10-20 23:15      Claude      [Fix] Initial tests for RetentionWriteError.
--------------------------------------------------------------------------------
"""

import errno
import os

import pytest

import raw_retention as rr


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path / "raw"))
    rr._LAST_SHA.clear()
    yield tmp_path / "raw"
    rr._LAST_SHA.clear()


def _fail_fsync(monkeypatch):
    """The line reaches the file, then the disk refuses to make it durable."""

    def fsync(_fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(rr.os, "fsync", fsync)


def _day(root):
    (path,) = (root / "acme").glob("*.ndjson")
    return path


def test_a_failed_append_raises_and_leaves_no_partial_line(root, monkeypatch):
    rr.retain("acme", b'{"v":1}')
    before = _day(root).read_bytes()
    _fail_fsync(monkeypatch)
    with pytest.raises(rr.RetentionWriteError, match="No space left"):
        rr.retain("acme", b'{"v":2}')
    # The earlier record is intact and the failed one is gone, not half there.
    assert _day(root).read_bytes() == before
    assert [blob for _c, _o, blob in rr.read_day("acme", _day(root).stem)] == [b'{"v":1}']


def test_a_failed_append_is_an_oserror(root, monkeypatch):
    """Callers that already treat OSError as a storage failure keep doing so."""
    _fail_fsync(monkeypatch)
    with pytest.raises(OSError):
        rr.record_outcome("acme", rr.OUTCOME_FETCH_ERROR, detail="x")


def test_a_payload_that_failed_to_store_is_stored_on_the_next_attempt(root, monkeypatch):
    """The dedup digest is only advanced once a payload is stored; otherwise the
    retry would be recorded as a duplicate of bytes that were never written."""
    real_fsync = os.fsync
    _fail_fsync(monkeypatch)
    with pytest.raises(rr.RetentionWriteError):
        rr.retain("acme", b'{"v":1}')
    monkeypatch.setattr(rr.os, "fsync", real_fsync)
    assert rr.retain("acme", b'{"v":1}') == rr.OUTCOME_OK
    assert [blob for _c, _o, blob in rr.read_day("acme", _day(root).stem)] == [b'{"v":1}']


def test_an_unsafe_key_is_still_a_value_error(root):
    with pytest.raises(ValueError):
        rr.retain("../evil", b"{}")


def test_a_short_write_then_a_full_disk_leaves_no_torn_line(root, monkeypatch):
    """The realistic torn write: part of the line reaches the file, then the
    disk is full. The fragment is removed and the next record stays readable."""
    rr.retain("acme", b'{"v":1}')
    before = _day(root).read_bytes()
    real_write, calls = os.write, []

    def write(fd, data):
        calls.append(len(data))
        if len(calls) == 1:
            return real_write(fd, bytes(data[: len(data) // 2]))
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(rr.os, "write", write)
    with pytest.raises(rr.RetentionWriteError):
        rr.retain("acme", b'{"v":2}')
    assert _day(root).read_bytes() == before
    monkeypatch.setattr(rr.os, "write", real_write)
    rr.retain("acme", b'{"v":3}')
    assert [blob for _c, _o, blob in rr.read_day("acme", _day(root).stem)] == [
        b'{"v":1}',
        b'{"v":3}',
    ]


def test_a_day_file_that_cannot_be_read_for_dedup_is_a_write_error(root, monkeypatch):
    """Every way retain() can fail to store raises the same error."""

    def unreadable(*a, **k):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(rr, "_tail_sha", unreadable)
    with pytest.raises(rr.RetentionWriteError):
        rr.retain("acme", b'{"v":1}')


def test_days_lists_the_retained_days_oldest_first(root):
    assert rr.days("acme") == []
    rr.retain("acme", b'{"v":1}')
    assert rr.days("acme") == [_day(root).stem]
