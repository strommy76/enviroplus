"""
--------------------------------------------------------------------------------
FILE:        conftest.py
PATH:        ~/projects/enviroplus/tests/conftest.py
DESCRIPTION: Test isolation for the canonical retention tier.

             A test suite must never be able to write into the canonical store.
             Retention is configured by a module-global root, so any test that
             causes it to be set to the production path leaves it set for the rest
             of the process.

             The call site owning that is fixed separately. This is the second
             line of defence: every test gets a throwaway root without opting in,
             so a collector that configures retention from a new place cannot
             reach production from a test run.

CHANGELOG:
2026-08-06 18:28      Claude     [Fix] Force every test onto a throwaway
                                      retention root.
--------------------------------------------------------------------------------
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_retention_root(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("ENVIRO_RAW_ROOT",
                       str(tmp_path_factory.mktemp("raw-capture-isolated")))
