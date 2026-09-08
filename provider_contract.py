#!/usr/bin/env python3
"""
--------------------------------------------------------------------------------
FILE:        provider_contract.py
PATH:        ~/projects/enviroplus/provider_contract.py
DESCRIPTION: Per-provider capture contract: a committed JSON document declares a
             provider's request shape (URL, query parameters resolved from .env
             key NAMES, timeout) and its response projection (a pivot over a
             list of observations with a vocabulary translating the provider's
             parameter names to store keys, typed row projections, and the
             derived table's declared columns). The collector executes any
             contract; a provider API change is a contract edit.

             Provider data is captured as stated: values, wall-clock and zone
             label are projected verbatim. Zone translation belongs to the
             client reading the store, never to capture.

             Boundary rule: a payload that arrives and parses but does not
             satisfy the declared shape is a ProjectionError -- the collector
             records it as `malformed`, writes no row, and the raw bytes stay in
             retention. Nothing is inferred, defaulted or dropped silently.

CHANGELOG:
2026-09-05 17:40      Claude     [Feature] Initial implementation (AirNow
                                      endpoint retirement 2026-09-30).
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

from shared.config_service import ConfigError, require

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"
# SQLite storage classes a declared column may carry, with the Python types a
# projected value must have to be stored without affinity conversion.
_STORAGE_CLASSES: dict[str, tuple[type, ...]] = {"INTEGER": (int,), "REAL": (int, float), "TEXT": (str,)}
# Joins the date and clock fields so one strptime call validates both against
# their formats. Must not be whitespace: strptime relaxes whitespace in the
# format to \s+, which would let a padded provider value through.
_JOIN = "|"


class ContractError(ConfigError):
    """The contract document does not satisfy the loader's schema."""


class ProjectionError(ValueError):
    """An arrived, parseable payload does not satisfy the declared projection."""


@dataclass(frozen=True)
class TimeOp:
    """Date string + clock string -> the provider's stated wall-clock as
    canonical text. Both fields must parse against their declared formats;
    nothing is converted -- the provider's statement is captured as-is and
    any zone translation is the client's."""

    date: str
    date_format: str
    clock: str
    clock_format: str


@dataclass(frozen=True)
class FieldOp:
    """Copy one field of the first observation."""

    field: str


@dataclass(frozen=True)
class Pivot:
    by: str
    vocabulary: Mapping[str, str]   # provider value -> store key
    columns: Mapping[str, str]      # "{key}_suffix" template -> item field


@dataclass(frozen=True)
class Contract:
    provider: str
    url: str
    params: Mapping[str, str]
    timeout_s: int
    poll_s: int
    pivot: Pivot
    row: Mapping[str, TimeOp | FieldOp]
    table: str
    primary_key: str
    columns: Mapping[str, str]      # column -> SQLite type

    def request_url(self) -> str:
        return f"{self.url}?{urlencode(self.params)}"

    def pivot_columns(self) -> tuple[str, ...]:
        keys = sorted(set(self.pivot.vocabulary.values()))
        return tuple(t.format(key=k) for k in keys for t in self.pivot.columns)

    def create_table_sql(self) -> str:
        defs = ", ".join(
            f"{col} {typ}" + (" PRIMARY KEY" if col == self.primary_key else "")
            for col, typ in self.columns.items()
        )
        return f"CREATE TABLE IF NOT EXISTS {self.table} ({defs})"


# ── Loader ─────────────────────────────────────────────────────────────────────

def _key(obj: Mapping[str, Any], key: str, ctx: str) -> Any:
    if not isinstance(obj, Mapping) or key not in obj:
        raise ContractError(f"{ctx}: missing required key {key!r}")
    return obj[key]


def _text(value: Any, ctx: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{ctx}: must be a non-empty string, got {value!r}")
    return value


def _positive_int(value: Any, ctx: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractError(f"{ctx}: must be a positive integer, got {value!r}")
    return value


def _str_mapping(value: Any, ctx: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ContractError(f"{ctx}: must be a non-empty object")
    return {_text(k, f"{ctx} key"): _text(v, f"{ctx}[{k!r}]") for k, v in value.items()}


def _resolve(spec: Any, ctx: str) -> str:
    """{"env": KEY} -> value of KEY from the environment; {"literal": v} -> v."""
    if isinstance(spec, Mapping) and set(spec) == {"env"}:
        key = _text(spec["env"], f"{ctx}.env")
        return _text(require(key), f"{ctx} (environment key {key})")
    if isinstance(spec, Mapping) and set(spec) == {"literal"}:
        return _text(spec["literal"], f"{ctx}.literal")
    raise ContractError(f"{ctx}: must be {{\"env\": KEY}} or {{\"literal\": value}}, got {spec!r}")


def _resolve_int(spec: Any, ctx: str) -> int:
    raw = _resolve(spec, ctx)
    try:
        value = int(raw)
    except ValueError:
        raise ContractError(f"{ctx}: resolved value {raw!r} is not an integer") from None
    return _positive_int(value, ctx)


def _time_op(spec: Mapping[str, Any], ctx: str) -> TimeOp:
    if not isinstance(spec, Mapping) or set(spec) != {"date", "date_format", "clock", "clock_format"}:
        raise ContractError(f"{ctx}: must declare exactly date, date_format, clock, clock_format")
    return TimeOp(**{k: _text(v, f"{ctx}.{k}") for k, v in spec.items()})


def _row_op(spec: Any, ctx: str) -> TimeOp | FieldOp:
    if isinstance(spec, Mapping) and set(spec) == {"time"}:
        return _time_op(spec["time"], f"{ctx}.time")
    if isinstance(spec, Mapping) and set(spec) == {"field"}:
        return FieldOp(field=_text(spec["field"], f"{ctx}.field"))
    raise ContractError(f"{ctx}: unknown projection op; expected {{\"time\": ...}} or {{\"field\": ...}}")


def _pivot(spec: Mapping[str, Any], ctx: str) -> Pivot:
    columns = _str_mapping(_key(spec, "columns", ctx), f"{ctx}.columns")
    for template in columns:
        try:
            rendered = template.format(key="k")
        except (KeyError, IndexError, ValueError):
            raise ContractError(f"{ctx}.columns: template {template!r} must reference only {{key}}") from None
        if rendered == template:
            raise ContractError(f"{ctx}.columns: template {template!r} does not reference {{key}}")
    return Pivot(
        by=_text(_key(spec, "by", ctx), f"{ctx}.by"),
        vocabulary=_str_mapping(_key(spec, "vocabulary", ctx), f"{ctx}.vocabulary"),
        columns=columns,
    )


def load_contract(path: str | Path) -> Contract:
    """Load and validate a contract; every {"env": KEY} is resolved now.

    Fails loud at load so a mis-edited contract stops the collector before its
    first poll instead of surfacing as a mis-attributed write error later.
    """
    path = Path(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"{path}: cannot read contract: {exc}") from exc
    if not isinstance(doc, Mapping):
        raise ContractError(f"{path}: contract root must be an object")
    ctx = path.name

    request = _key(doc, "request", ctx)
    params_spec = _key(request, "params", f"{ctx}.request")
    if not isinstance(params_spec, Mapping):
        raise ContractError(f"{ctx}.request.params: must be an object")
    params = {_text(k, f"{ctx}.request.params key"): _resolve(v, f"{ctx}.request.params[{k!r}]")
              for k, v in params_spec.items()}

    response = _key(doc, "response", ctx)
    pivot = _pivot(_key(response, "pivot", f"{ctx}.response"), f"{ctx}.response.pivot")
    row_spec = _key(response, "row", f"{ctx}.response")
    if not isinstance(row_spec, Mapping) or not row_spec:
        raise ContractError(f"{ctx}.response.row: must be a non-empty object")
    row = {_text(col, f"{ctx}.response.row key"): _row_op(op, f"{ctx}.response.row[{col!r}]")
           for col, op in row_spec.items()}

    store = _key(doc, "store", ctx)
    columns = _str_mapping(_key(store, "columns", f"{ctx}.store"), f"{ctx}.store.columns")
    for column, typ in columns.items():
        if typ not in _STORAGE_CLASSES:
            raise ContractError(f"{ctx}.store.columns[{column!r}]: storage class must be one of "
                                f"{sorted(_STORAGE_CLASSES)}, got {typ!r}")
    primary_key = _text(_key(store, "primary_key", f"{ctx}.store"), f"{ctx}.store.primary_key")

    contract = Contract(
        provider=_text(_key(doc, "provider", ctx), f"{ctx}.provider"),
        url=_text(_key(request, "url", f"{ctx}.request"), f"{ctx}.request.url"),
        params=params,
        timeout_s=_positive_int(_key(request, "timeout_s", f"{ctx}.request"), f"{ctx}.request.timeout_s"),
        poll_s=_resolve_int(_key(doc, "poll_s", ctx), f"{ctx}.poll_s"),
        pivot=pivot,
        row=row,
        table=_text(_key(store, "table", f"{ctx}.store"), f"{ctx}.store.table"),
        primary_key=primary_key,
        columns=columns,
    )

    produced = set(contract.pivot_columns()) | set(row)
    if len(produced) != len(contract.pivot_columns()) + len(row):
        raise ContractError(f"{ctx}: pivot columns and row columns overlap")
    declared = set(columns)
    if produced != declared:
        raise ContractError(
            f"{ctx}: produced columns must equal store.columns; "
            f"undeclared={sorted(produced - declared)} never_produced={sorted(declared - produced)}")
    if primary_key not in row or not isinstance(row[primary_key], TimeOp):
        raise ContractError(f"{ctx}.store.primary_key: {primary_key!r} must be a time projection "
                            "(the derived row is keyed by the provider's stated observation time)")
    for column, op in row.items():
        if isinstance(op, TimeOp) and columns[column] != "TEXT":
            raise ContractError(f"{ctx}.store.columns[{column!r}]: a time projection is TEXT, declared {columns[column]!r}")
    return contract


# ── Projection ─────────────────────────────────────────────────────────────────

def _time(op: TimeOp, item: Mapping[str, Any]) -> str:
    date, clock = item.get(op.date), item.get(op.clock)
    if not isinstance(date, str) or not isinstance(clock, str):
        raise ProjectionError(f"{op.date!r}/{op.clock!r} must both be strings, got {date!r}/{clock!r}")
    try:
        stated = datetime.strptime(f"{date}{_JOIN}{clock}", f"{op.date_format}{_JOIN}{op.clock_format}")
    except ValueError as exc:
        raise ProjectionError(f"time fields {date!r} {clock!r} do not match declared formats: {exc}") from None
    return stated.strftime(_TS_FORMAT)


def _typed(contract: Contract, column: str, value: Any) -> Any:
    """A projected value is stored only if it already has the declared storage class.

    SQLite affinity would otherwise convert it silently ("11" -> 11, True -> 1),
    which is a change to captured provider data.
    """
    if value is None:
        return None
    allowed = _STORAGE_CLASSES[contract.columns[column]]
    if isinstance(value, bool) or not isinstance(value, allowed):
        raise ProjectionError(
            f"{column}: value {value!r} is not {contract.columns[column]} as declared")
    return value


def _source_fields(op: TimeOp | FieldOp) -> tuple[str, ...]:
    return (op.date, op.clock) if isinstance(op, TimeOp) else (op.field,)


def project(contract: Contract, data: Any) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Project a parsed payload to one derived row.

    Returns (row, absent_columns). The row holds only the columns this arrival
    states (a field sent as null is a statement of null). A declared parameter
    or row field the provider did not send is left out of the row and named in
    absent_columns -- a true provider state the caller records as `partial`.
    Anything outside the declared shape raises ProjectionError: an item
    without the pivot key, a parameter name outside the vocabulary, two items
    resolving to one store key, an item lacking a declared field, items
    disagreeing on a row-level field, a value whose
    type is not the declared storage class, or time fields that do not parse.
    """
    pivot = contract.pivot
    if not isinstance(data, list) or not data:
        raise ProjectionError("payload is not a non-empty list of observations")
    items: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(data):
        if not isinstance(item, Mapping):
            raise ProjectionError(f"item {index} is not an object")
        if pivot.by not in item:
            raise ProjectionError(f"item {index} lacks pivot key {pivot.by!r}")
        value = item[pivot.by]
        if not isinstance(value, str) or value not in pivot.vocabulary:
            raise ProjectionError(f"undeclared {pivot.by} value {value!r}")
        key = pivot.vocabulary[value]
        if key in items:
            raise ProjectionError(f"two items resolve to store key {key!r}")
        items[key] = item

    # The row carries only what the provider STATED in this arrival. A declared
    # parameter the provider did not send is absent from the row (named in
    # `absent`), never written as NULL: on insert the column is NULL because
    # nothing was ever stated, and on a later statement it keeps the value the
    # provider stated before -- one arrival cannot withdraw another's
    # assertion by omission. A field sent as null IS a statement and is
    # written as NULL.
    row: dict[str, Any] = {}
    absent: list[str] = []
    for key in sorted(set(pivot.vocabulary.values())):
        item = items.get(key)
        for template, field in pivot.columns.items():
            column = template.format(key=key)
            if item is None:
                absent.append(column)
                continue
            if field not in item:
                raise ProjectionError(f"item {item[pivot.by]!r} lacks declared field {field!r}")
            row[column] = _typed(contract, column, item[field])

    # Row-level fields describe the observation set as a whole, so every item
    # must state them identically; otherwise the row would depend on the order
    # the provider happened to list its items in.
    first = data[0]
    for op in contract.row.values():
        for field in _source_fields(op):
            # An omitted field and a field sent as null are different statements
            # (one keeps the earlier value, the other overwrites it), so they
            # must not collapse into one reading of "agreement".
            stated = {json.dumps(item[field], sort_keys=True, default=repr) if field in item else "<unstated>"
                      for item in data}
            if len(stated) > 1:
                raise ProjectionError(f"items disagree on {field!r}: {sorted(stated)}")
    for column, op in contract.row.items():
        if isinstance(op, TimeOp):
            row[column] = _time(op, first)
        elif op.field not in first:
            absent.append(column)
        else:
            row[column] = _typed(contract, column, first[op.field])
    return row, tuple(absent)
