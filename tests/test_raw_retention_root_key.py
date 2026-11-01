"""The dedup digest cache belongs to the store it was read from: a root change
must not carry the previous root's last digest across (that labelled the first
arrival into a new root `duplicate` and dropped its bytes)."""

import raw_retention as rr


def test_same_store_under_another_spelling_still_dedups(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path / "a"))
    assert rr.retain("acme", b'[{"v": 2}]') == rr.OUTCOME_OK
    monkeypatch.setenv("ENVIRO_RAW_ROOT", str(tmp_path / "x" / ".." / "a"))
    assert rr.retain("acme", b'[{"v": 2}]') == rr.OUTCOME_DUPLICATE


def test_relative_root_under_a_cwd_change_is_two_stores(tmp_path, monkeypatch):
    """The key resolves the root: a relative root read from two working
    directories is two stores, and the second must store the first arrival."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.delenv("ENVIRO_RAW_ROOT", raising=False)
    rr.configure("raw")
    monkeypatch.chdir(tmp_path / "a")
    assert rr.retain("acme", b'[{"v": 3}]') == rr.OUTCOME_OK
    monkeypatch.chdir(tmp_path / "b")
    assert rr.retain("acme", b'[{"v": 3}]') == rr.OUTCOME_OK
    assert (tmp_path / "b" / "raw" / "acme").exists()
