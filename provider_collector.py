#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        provider_collector.py
PATH:        ~/projects/enviroplus/provider_collector.py
DESCRIPTION: Generic provider collector. Executes one capture contract
             (provider_contract.py): fetch -> classify -> retain the bytes as
             received (canonical) -> project through the contract -> write the
             derived row. One arrival outcome per attempt; a write failure is
             recorded as a write failure, not a fetch failure.

             Usage: provider_collector.py --contract contracts/<provider>.json

CHANGELOG:
2026-09-05 17:40      Claude     [Feature] Initial implementation; replaces the
                                      hardcoded airnow_wx.py collector.
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable

from provider_contract import Contract, ProjectionError, load_contract, project
from shared.config_service import ConfigError, load_env, require
from shared.db_service import connect, write_row
from shared.logging_service import setup_logger
from shared.raw_retention import (
    OUTCOME_EMPTY,
    OUTCOME_FETCH_ERROR,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_PARTIAL,
    OUTCOME_WRITE_ERROR,
    configure as configure_retention,
    record_outcome,
    retain,
)
from shared.signal_handler import install_shutdown_handler

_BASE = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BASE, ".env")

# Structural constant: bounds shutdown latency to one second. It cannot bind
# nominal behaviour because every provider's poll interval is minutes to hours.
_SHUTDOWN_CHECK_S = 1


def classify_response(raw: bytes):
    """Label an arrived payload: (parsed_or_None, outcome, detail). Pure.

    Only an empty list is `empty`; any other parseable body is handed to the
    contract, which decides whether it satisfies the declared shape.
    """
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, OUTCOME_MALFORMED, str(exc)
    if data == []:
        return data, OUTCOME_EMPTY, "provider returned no observations"
    return data, OUTCOME_OK, None


def outcome_for_exception(exc: BaseException) -> str:
    """A failed derived write is not a failed fetch."""
    if isinstance(exc, sqlite3.Error):
        return OUTCOME_WRITE_ERROR
    return OUTCOME_FETCH_ERROR


@dataclass
class Collector:
    contract: Contract
    db: sqlite3.Connection
    log: object

    def fetch(self) -> bytes:
        request = urllib.request.Request(self.contract.request_url())
        with urllib.request.urlopen(request, timeout=self.contract.timeout_s) as response:
            return response.read()

    def attempt(self) -> bool:
        """One poll. Returns True when a derived row was written (inserted or updated).

        The arrival is retained exactly once, carrying the outcome the payload
        actually earned: `ok`, `partial` (a declared parameter absent), or
        `malformed` (unparseable, or outside the declared shape). Projection is
        pure, so it runs before retention and cannot lose the bytes.
        """
        provider = self.contract.provider
        url = self.contract.request_url()
        raw = self.fetch()

        data, outcome, detail = classify_response(raw)
        row, absent = None, ()
        if outcome == OUTCOME_OK:
            try:
                row, absent = project(self.contract, data)
            except ProjectionError as exc:
                outcome, detail = OUTCOME_MALFORMED, f"declared projection not satisfied: {exc}"
            else:
                if absent:
                    outcome, detail = OUTCOME_PARTIAL, "absent from response: " + ", ".join(absent)
        try:
            retain(provider, raw, url=url, outcome=outcome, detail=detail)
        except Exception as exc:  # retention failure must not lose the derived row too
            self.log.error("raw retention failed for %s: %s", provider, exc, exc_info=True)

        if row is None:
            (self.log.error if outcome == OUTCOME_MALFORMED else self.log.info)("%s: %s", provider, detail)
            return False
        if absent:
            self.log.warning("%s: %s", provider, detail)
        # The derived row is keyed by the provider's stated observation time and
        # follows the provider's latest statement: a revision within the hour
        # overwrites the earlier projection, and a restatement rewrites the same
        # values (idempotent). Whether the row exists is never inferred from the
        # retention tier's dedup answer: the derived store is its own truth.
        # Every statement stays in retention, so the projection can be
        # re-derived under different logic later.
        written = write_row(self.db, self.contract.table, row, upsert_on=self.contract.primary_key)
        if written:
            self.log.info("%s row written  %s=%s", provider, self.contract.primary_key,
                          row[self.contract.primary_key])
        return written

    def run(self, is_shutting_down: Callable[[], bool], sleep: Callable[[float], None] = time.sleep) -> None:
        provider = self.contract.provider
        self.log.info("%s collector starting  url=%s  poll_s=%d", provider,
                      self.contract.url, self.contract.poll_s)
        while not is_shutting_down():
            try:
                self.attempt()
            except Exception as exc:
                record_outcome(provider, outcome_for_exception(exc), detail=repr(exc),
                               url=self.contract.request_url())
                self.log.error("%s attempt failed: %s", provider, exc, exc_info=True)
            waited = 0
            while waited < self.contract.poll_s and not is_shutting_down():
                sleep(_SHUTDOWN_CHECK_S)
                waited += _SHUTDOWN_CHECK_S
        self.log.info("%s collector stopped", provider)


def ensure_table(db: sqlite3.Connection, contract: Contract) -> None:
    """Make the derived table match the contract's declaration, or refuse.

    A declared column the table lacks is added by ALTER with no DEFAULT: NULL
    on existing rows states that the value was not captured for them. A table
    column the contract does not declare, a storage class that differs, or a
    primary key that differs is a contract/table disagreement and fails loud
    rather than being written around forever.
    """
    db.execute(contract.create_table_sql())
    existing = {r[1]: (r[2].upper(), r[5] > 0)
                for r in db.execute(f"PRAGMA table_info({contract.table})")}
    undeclared = sorted(set(existing) - set(contract.columns))
    if undeclared:
        raise ConfigError(f"table {contract.table!r} has columns the contract does not declare: {undeclared}")
    for column, typ in contract.columns.items():
        if column not in existing:
            db.execute(f"ALTER TABLE {contract.table} ADD COLUMN {column} {typ}")
            continue
        actual_type, is_pk = existing[column]
        if actual_type != typ.upper() or is_pk != (column == contract.primary_key):
            raise ConfigError(
                f"table {contract.table!r} column {column!r} is {actual_type}"
                f"{' PRIMARY KEY' if is_pk else ''}; contract declares {typ}"
                f"{' PRIMARY KEY' if column == contract.primary_key else ''}")
    db.commit()


def build(contract_path: str, *, env_path: str = _ENV_PATH) -> Collector:
    """Resolve configuration and open the seams; no polling happens here."""
    load_env(env_path, expect_key="SQLITE_PATH")
    contract = load_contract(contract_path)
    configure_retention(os.environ.get("ENVIRO_RAW_ROOT", os.path.join(_BASE, "raw-capture")))
    db = connect(require("SQLITE_PATH"))
    ensure_table(db, contract)
    log = setup_logger(f"{contract.provider}_collector", require("LOG_PATH"))
    return Collector(contract=contract, db=db, log=log)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Execute one provider capture contract.")
    parser.add_argument("--contract", required=True, help="path to the contract JSON")
    args = parser.parse_args(argv)
    collector = build(args.contract)
    is_shutting_down = install_shutdown_handler(logger=collector.log)
    collector.run(is_shutting_down)


if __name__ == "__main__":
    main()
