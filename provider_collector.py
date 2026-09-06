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
                    provider_collector.py --contract ... --replay DAY [DAY ...]
             Replay re-derives the derived rows for named observation dates
             from canonical retention through the same projection and write
             path live uses; selection is by the data's inherent date.

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
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

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
    read_day,
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


@dataclass(frozen=True)
class Arrival:
    """What one arrived payload earned: its outcome, and the row it projects to (if any)."""

    outcome: str
    detail: str | None
    row: dict[str, Any] | None
    absent: tuple[str, ...]


def project_arrival(contract: Contract, raw: bytes) -> Arrival:
    """Classify and project one payload. Pure: live capture and replay both use it,
    so a row derived from retention is the row live would have written."""
    data, outcome, detail = classify_response(raw)
    if outcome != OUTCOME_OK:
        return Arrival(outcome, detail, None, ())
    try:
        row, absent = project(contract, data)
    except ProjectionError as exc:
        return Arrival(OUTCOME_MALFORMED, f"declared projection not satisfied: {exc}", None, ())
    if absent:
        return Arrival(OUTCOME_PARTIAL, "absent from response: " + ", ".join(absent), row, absent)
    return Arrival(OUTCOME_OK, None, row, ())


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
        arrival = project_arrival(self.contract, raw)
        try:
            retain(provider, raw, url=url, outcome=arrival.outcome, detail=arrival.detail)
        except Exception as exc:  # retention failure must not lose the derived row too
            self.log.error("raw retention failed for %s: %s", provider, exc, exc_info=True)
        return self.write(arrival)

    def write(self, arrival: Arrival) -> bool:
        """Write the derived row an arrival projects to; shared by live and replay."""
        provider = self.contract.provider
        if arrival.row is None:
            (self.log.error if arrival.outcome == OUTCOME_MALFORMED else self.log.info)(
                "%s: %s", provider, arrival.detail)
            return False
        if arrival.absent:
            self.log.warning("%s: %s", provider, arrival.detail)
        # The derived row is keyed by the provider's stated observation time and
        # follows the provider's latest statement: a revision within the hour
        # overwrites the earlier projection, and a restatement rewrites the same
        # values (idempotent). Whether the row exists is never inferred from the
        # retention tier's dedup answer: the derived store is its own truth.
        # Every statement stays in retention, so the projection can be
        # re-derived under different logic later.
        written = write_row(self.db, self.contract.table, arrival.row, upsert_on=self.contract.primary_key)
        if written:
            self.log.info("%s row written  %s=%s", provider, self.contract.primary_key,
                          arrival.row[self.contract.primary_key])
        return written

    def replay(self, days: list[str], *, today: str | None = None) -> dict[str, Any]:
        """Re-derive the derived rows whose OBSERVATION date (the provider's stated
        date, the row key) falls on the named days.

        Selection is by the data's inherent date, never by when it was pulled:
        a statement about observation day D can only have been captured on D or
        later, so retention is scanned from the earliest named day through
        today (UTC) in capture order, and every projected row dated inside the
        named days is written through the same write path live uses. Later
        statements captured on later days therefore always win. Statements about
        other dates met in the scan are counted, not written. Retention is never
        written. Returns a determinate summary keyed by the outcome each payload
        earns now (a retained outcome is a proxy; content decides).
        """
        provider = self.contract.provider
        wanted = sorted(set(days))
        last = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        scan = _utc_days_between(wanted[0], last)
        tally: Counter = Counter()
        for day in scan:
            for _captured, recorded_outcome, blob in read_day(provider, day):
                tally["records"] += 1
                if blob is None:
                    tally["without_payload"] += 1
                    continue
                arrival = project_arrival(self.contract, blob)
                tally["projected"] += 1
                tally[arrival.outcome] += 1
                if arrival.outcome != recorded_outcome:
                    tally["reclassified"] += 1
                if arrival.row is None:
                    self.write(arrival)          # logs the malformed/empty statement like live does
                    continue
                if str(arrival.row[self.contract.primary_key])[:10] not in wanted:
                    tally["other_dates"] += 1
                    continue
                if self.write(arrival):
                    tally["written"] += 1
        return {"provider": provider, "days": wanted, "capture_days_scanned": len(scan),
                **{k: tally[k] for k in ("records", "without_payload", "projected", "other_dates", "written",
                                         OUTCOME_OK, OUTCOME_PARTIAL, OUTCOME_EMPTY, OUTCOME_MALFORMED, "reclassified")}}

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


def _utc_days_between(first: str, last: str) -> list[str]:
    start, end = datetime.strptime(first, "%Y-%m-%d"), datetime.strptime(last, "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]


def _utc_day(text: str) -> str:
    """A --replay argument names one observation date; anything else is a client error."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a UTC day in YYYY-MM-DD form") from None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Execute one provider capture contract.")
    parser.add_argument("--contract", required=True, help="path to the contract JSON")
    parser.add_argument("--replay", nargs="+", metavar="DAY", type=_utc_day,
                        help="re-derive the derived rows whose observation date (the provider's stated date) is one of "
                             "these days (YYYY-MM-DD), from every retained statement about them, and exit; writes to "
                             "the database named by SQLITE_PATH -- point it at a scratch file to rebuild aside")
    args = parser.parse_args(argv)
    collector = build(args.contract)
    if args.replay:
        print(json.dumps(collector.replay(args.replay)))
        return
    is_shutting_down = install_shutdown_handler(logger=collector.log)
    collector.run(is_shutting_down)


if __name__ == "__main__":
    main()
