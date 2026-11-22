"""Deterministic validators (research.md R-1, R-2, R-5 … R-7, R-17).

- A JSON Schema validator for exactly the keyword subset declared in R-1 (no dependency).
- `check_output`: the schema-1.0 contract (OUT-SCHEMA) plus the calendar-date check (OUT-DATE).

Every error is a `ValidationError(code, pointer, message, layer)`, with codes and layers from the
spec FR-028 table. Errors are collected, never stopped at the first.
"""

from __future__ import annotations

import copy
import datetime
import functools
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

MR_VERSION = "mr-1"

ASSERTION_KEYWORDS = frozenset(
    {
        "type",
        "enum",
        "const",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "pattern",
        "exclusiveMinimum",
        "maxProperties",
        "anyOf",
        "allOf",
        "if",
        "then",
        "$ref",
    }
)
ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "$defs", "title", "description", "$comment"})

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class UnsupportedKeyword(Exception):
    """A schema uses a keyword outside the R-1 subset, so the validator would ignore it."""


@dataclass(frozen=True)
class ValidationError:
    """One failed check. `keyword` is set for raw schema errors only."""

    code: str
    pointer: str
    message: str
    layer: int
    keyword: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        del data["keyword"]
        return data


# ------------------------------------------ schema files ------------------------------------------


def schema_path(name: str) -> Path:
    """`schemas/<name>.schema.json`, resolved from the project root (editable install, R-2)."""
    return Path(__file__).resolve().parents[2] / "schemas" / f"{name}.schema.json"


@functools.cache
def _load_schema_cached(name: str) -> dict:
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def load_schema(name: str) -> dict:
    """A fresh copy of the named schema, so callers cannot change the cached one."""
    return copy.deepcopy(_load_schema_cached(name))


# ---------------------------------------- the R-1 validator ---------------------------------------


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _json_equal(a, b) -> bool:
    """JSON equality: booleans are not numbers, 1 equals 1.0, containers compare deeply."""
    kind = _kind(a)
    if kind != _kind(b):
        return False
    if kind == "array":
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b, strict=True))
    if kind == "object":
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    return a == b


def _is_type(value, name: str) -> bool:
    if name == "integer":
        return _kind(value) == "number" and float(value).is_integer()
    return _kind(value) == name


def _check_supported(schema, where: str = "#") -> None:
    """Walk the whole schema and refuse any keyword outside the R-1 subset."""
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key not in ASSERTION_KEYWORDS and key not in ANNOTATION_KEYWORDS:
            raise UnsupportedKeyword(f"unsupported schema keyword {key!r} at {where}")
        if key == "$ref" and not (isinstance(value, str) and value.startswith("#")):
            raise UnsupportedKeyword(f"only local $ref is supported, got {value!r} at {where}")
        if key in ("properties", "$defs"):
            for sub_name, sub in value.items():
                _check_supported(sub, f"{where}/{key}/{sub_name}")
        elif key in ("items", "if", "then", "additionalProperties"):
            _check_supported(value, f"{where}/{key}")
        elif key in ("anyOf", "allOf"):
            for index, sub in enumerate(value):
                _check_supported(sub, f"{where}/{key}/{index}")


def _resolve(root: dict, ref: str) -> dict:
    node = root
    for token in ref[1:].split("/")[1:] if ref != "#" else []:
        node = node[token.replace("~1", "/").replace("~0", "~")]
    return node


def _pattern_matches(pattern: str, text: str) -> bool:
    # ECMA-262 `$` (no multiline) matches only at the very end, unlike Python's `$`, which also
    # matches before a final newline.
    if pattern.endswith("$") and not pattern.endswith("\\$"):
        pattern = pattern[:-1] + r"\Z"
    return re.search(pattern, text) is not None


class _Validator:
    def __init__(self, root: dict, code: str, layer: int):
        self.root = root
        self.code = code
        self.layer = layer

    def error(self, pointer: str, keyword: str, message: str) -> ValidationError:
        return ValidationError(self.code, pointer, message, self.layer, keyword)

    def run(self, value, schema, pointer: str) -> list[ValidationError]:
        if not isinstance(schema, dict):
            return []
        errors: list[ValidationError] = []
        if "$ref" in schema:
            errors += self.run(value, _resolve(self.root, schema["$ref"]), pointer)
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_is_type(value, name) for name in names):
                errors.append(
                    self.error(
                        pointer, "type", f"expected {' or '.join(names)}, got {_kind(value)}"
                    )
                )
        if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
            errors.append(
                self.error(pointer, "enum", f"{value!r} is not one of {schema['enum']!r}")
            )
        if "const" in schema and not _json_equal(value, schema["const"]):
            errors.append(self.error(pointer, "const", f"{value!r} is not {schema['const']!r}"))
        kind = _kind(value)
        if kind == "string":
            errors += self._string(value, schema, pointer)
        elif kind == "number":
            if "exclusiveMinimum" in schema and not value > schema["exclusiveMinimum"]:
                errors.append(
                    self.error(
                        pointer,
                        "exclusiveMinimum",
                        f"{value!r} is not > {schema['exclusiveMinimum']}",
                    )
                )
        elif kind == "array":
            errors += self._array(value, schema, pointer)
        elif kind == "object":
            errors += self._object(value, schema, pointer)
        if "anyOf" in schema and not any(
            not self.run(value, sub, pointer) for sub in schema["anyOf"]
        ):
            errors.append(self.error(pointer, "anyOf", "does not match any anyOf alternative"))
        for sub in schema.get("allOf", []):
            errors += self.run(value, sub, pointer)
        if "if" in schema and not self.run(value, schema["if"], pointer):
            errors += self.run(value, schema.get("then", {}), pointer)
        return errors

    def _string(self, value: str, schema: dict, pointer: str) -> list[ValidationError]:
        errors = []
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                self.error(pointer, "minLength", f"length {len(value)} < {schema['minLength']}")
            )
        if "pattern" in schema and not _pattern_matches(schema["pattern"], value):
            errors.append(
                self.error(pointer, "pattern", f"{value!r} does not match {schema['pattern']!r}")
            )
        return errors

    def _array(self, value: list, schema: dict, pointer: str) -> list[ValidationError]:
        errors = []
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                self.error(pointer, "minItems", f"{len(value)} items < {schema['minItems']}")
            )
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(
                self.error(pointer, "maxItems", f"{len(value)} items > {schema['maxItems']}")
            )
        if schema.get("uniqueItems"):
            for i, item in enumerate(value):
                if any(_json_equal(item, earlier) for earlier in value[:i]):
                    errors.append(self.error(f"{pointer}/{i}", "uniqueItems", "duplicate item"))
        if "items" in schema:
            for i, item in enumerate(value):
                errors += self.run(item, schema["items"], f"{pointer}/{i}")
        return errors

    def _object(self, value: dict, schema: dict, pointer: str) -> list[ValidationError]:
        errors = []
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(self.error(pointer, "required", f"missing required key {key!r}"))
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(
                self.error(
                    pointer, "maxProperties", f"{len(value)} keys > {schema['maxProperties']}"
                )
            )
        for key, item in value.items():
            child = f"{pointer}/{_escape(key)}"
            if key in properties:
                errors += self.run(item, properties[key], child)
            elif schema.get("additionalProperties") is False:
                errors.append(self.error(child, "additionalProperties", f"unexpected key {key!r}"))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors += self.run(item, schema["additionalProperties"], child)
        return errors


def validate(instance, schema: dict, *, code: str = "SCHEMA", layer: int = 1):
    """Validate `instance` against `schema` (R-1 subset). Returns every error found.

    Raises `UnsupportedKeyword` if the schema uses a keyword outside the subset.
    """
    _check_supported(schema)
    return _Validator(schema, code, layer).run(instance, schema, "")


# ------------------------------------------- output 1.0 -------------------------------------------


def check_output(result) -> list[ValidationError]:
    """OUT-SCHEMA (schema 1.0 incl. FR-015 shapes) and OUT-DATE (calendar date), both layer 1."""
    errors = validate(result, _load_schema_cached("output"), code="OUT-SCHEMA", layer=1)
    date = result.get("announcement_date") if isinstance(result, dict) else None
    if isinstance(date, str) and _DATE_PATTERN.fullmatch(date):
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            errors.append(
                ValidationError(
                    "OUT-DATE", "/announcement_date", f"{date!r} is not a calendar date", 1
                )
            )
    return errors


# --------------------------------------------- helpers --------------------------------------------

TOP_EVIDENCE_FIELDS = (
    "company",
    "announcement_date",
    "order_value",
    "currency",
    "unit",
    "client",
    "order_type",
    "execution_period",
)
ORDER_EVIDENCE_FIELDS = TOP_EVIDENCE_FIELDS[2:]
ADDITIONAL_EVIDENCE_FIELDS = ("order_value", "currency", "unit", "client")
REQUIRED_ORDER_FIELDS = ("order_value", "client")
LEGAL_SUFFIXES = frozenset({"limited", "ltd", "private", "pvt", "inc", "llp", "plc", "corp", "co"})
# R-7 G-5: the stock exchanges and the regulator (spec FR-028 code table).
EXCHANGE_NAMES = (
    "BSE Limited",
    "BSE Ltd",
    "National Stock Exchange of India Limited",
    "NSE",
    "SEBI",
    "Securities and Exchange Board of India",
)

_WHITESPACE = re.compile(r"\s+")


def ws_norm(text: str) -> str:
    """Replace every run of Unicode whitespace (NBSP included) with one space, then trim."""
    return _WHITESPACE.sub(" ", text).strip()


def canon_digits(value) -> str:
    """Canonical decimal digits of a value: 1250.5 -> "12505", 4500000 -> "4500000"."""
    return format(Decimal(str(value)).normalize(), "f").replace(".", "").lstrip("-")


def digits_only(quote: str) -> str:
    """The ASCII digits of a quote: "₹1,250.50 crore" -> "125050"."""
    return "".join(ch for ch in quote if ch in "0123456789")


def name_norm(name: str) -> str:
    """FR-029 name normalisation: casefold, & -> and, drop punctuation, collapse whitespace,
    then repeatedly drop a trailing legal suffix token."""
    text = name.casefold().replace("&", " and ")
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    tokens = ws_norm(text).split(" ") if ws_norm(text) else []
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


EXCHANGE_DENYLIST = frozenset(name_norm(name) for name in EXCHANGE_NAMES)


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


# ------------------------------------------ value_in_cr (R-17) ------------------------------------

# FR-035: the owner's crore multipliers, as exact decimal strings.
CRORE_MULTIPLIER = {
    "crore": "1",
    "lakh": "0.01",
    "million": "0.1",
    "billion": "100",
    "thousand": "0.0001",
    "absolute": "0.0000001",
}


def value_in_cr(order_value, currency, unit) -> float | None:
    """FR-035: an INR amount in crore, exact decimal arithmetic rounded half up to 4 places.
    None for USD, EUR, other and a null currency or value (no FX conversion)."""
    if currency != "INR" or order_value is None:
        return None
    exact = Decimal(str(order_value)) * Decimal(CRORE_MULTIPLIER[unit])
    return float(exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


# ---------------------------------------- ranking (R-6, FR-009) -----------------------------------

# FR-009 base-value factors and reference FX rates, used for ranking only and never applied to
# a reported value or to value_in_cr. The FX rates are CONFIRMED by Balakrishnan 2026-11-22 (P-1.5).
UNIT_FACTOR = {
    "crore": 10_000_000,
    "lakh": 100_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "thousand": 1_000,
    "absolute": 1,
}
FX_RATE = {"INR": 1, "USD": 84, "EUR": 90}


def base_value(order: dict) -> Decimal | None:
    """INR-equivalent base value of a valued INR/USD/EUR order; None otherwise."""
    value, currency, unit = order.get("order_value"), order.get("currency"), order.get("unit")
    if not _is_number(value) or currency not in FX_RATE or unit not in UNIT_FACTOR:
        return None
    return Decimal(str(value)) * UNIT_FACTOR[unit] * FX_RATE[currency]


def ranking_key(order: dict) -> tuple:
    """R-6: valued INR/USD/EUR orders first, largest base value first; then valued `other`
    orders; then orders with no value. Ties keep the stated order (stable sort). Never reads
    value_in_cr."""
    base = base_value(order)
    if base is not None:
        return (0, -base)
    if order.get("order_value") is not None:
        return (1, 0)
    return (2, 0)


def rank(orders: list[dict]) -> tuple[int, list[int]]:
    """(top-level index, additional indices): the first-ranked order, then the rest with valued
    ones in order of appearance followed by the ones with no value in order of appearance."""
    top = sorted(range(len(orders)), key=lambda i: ranking_key(orders[i]))[0]
    rest = [i for i in range(len(orders)) if i != top]
    valued = [i for i in rest if orders[i].get("order_value") is not None]
    return top, valued + [i for i in rest if orders[i].get("order_value") is None]


def _ranking_errors(result: dict) -> list[ValidationError]:
    """C-2: spec INV-9 (rev 2) clauses (i) and (iii); (ii) never compares an `other` order."""
    order = result.get("order") if isinstance(result.get("order"), dict) else None
    extras = result.get("additional_orders")
    extras = [e for e in extras if isinstance(e, dict)] if isinstance(extras, list) else []
    if order is None or not extras:
        return []
    errors = []
    top_base = base_value(order)
    for i, extra in enumerate(extras):
        extra_base = base_value(extra)
        if extra_base is not None and (top_base is None or top_base < extra_base):
            errors.append(
                ValidationError(
                    "C-2",
                    f"/additional_orders/{i}",
                    "INV-9 (i): an additional order ranks above the top-level order (FR-009)",
                    2,
                )
            )
    if order.get("currency") == "other":
        valued = [o for o in [order, *extras] if o.get("order_value") is not None]
        if len(valued) != 1:
            errors.append(
                ValidationError(
                    "C-2",
                    "/order/currency",
                    "INV-9 (iii): a top-level `other` order must be the only valued order",
                    2,
                )
            )
    return errors


# ------------------------------------------- MR checks --------------------------------------------

_MR_TOP_PAIRS = (
    ("company", "company_quote"),
    ("announcement_date", "announcement_date_quote"),
    ("order_type", "order_type_quote"),
    ("execution_period", "execution_period_quote"),
)


def _mr_consistency(mr: dict) -> list[ValidationError]:
    errors = []

    def fail(pointer, message):
        errors.append(ValidationError("MR-CONSIST", pointer, message, 1))

    # MC-1: the is_new_order rules (FR-005, FR-015).
    if mr["is_new_order"]:
        if not mr["orders"]:
            fail("/orders", "MC-1: is_new_order true needs at least one order entry")
        if mr["order_type"] is None:
            fail("/order_type", "MC-1: is_new_order true needs an order_type")
    else:
        if mr["orders"]:
            fail("/orders", "MC-1: is_new_order false needs orders []")
        for field in (
            "order_type",
            "order_type_quote",
            "execution_period",
            "execution_period_quote",
        ):
            if mr[field] is not None:
                fail(f"/{field}", f"MC-1: is_new_order false needs {field} null")

    # MC-2: each value and its quote are both null or both non-null.
    for field, quote in _MR_TOP_PAIRS:
        if (mr[field] is None) != (mr[quote] is None):
            fail(f"/{quote}", f"MC-2: {field} and {quote} must both be null or both be set")
    for i, order in enumerate(mr["orders"]):
        if (order["client"] is None) != (order["client_quote"] is None):
            fail(f"/orders/{i}/client_quote", "MC-2: client and client_quote must pair")
        # MC-3: currency, unit and value_quote are null iff order_value is null.
        for key in ("currency", "unit", "value_quote"):
            if (order["order_value"] is None) != (order[key] is None):
                fail(f"/orders/{i}/{key}", f"MC-3: {key} must be null iff order_value is null")
    return errors


def check_mr(obj) -> list[ValidationError]:
    """MR-SCHEMA (mr-1) first; on a schema-valid response, MR-CONSIST (MC-1 … MC-3)."""
    errors = validate(obj, _load_schema_cached("model-response"), code="MR-SCHEMA", layer=1)
    if errors:
        return errors
    return _mr_consistency(obj)


# ------------------------------------------ post-validation ---------------------------------------


def _orders_with_pointers(result: dict):
    """(order dict, its evidence dict, pointer) for the top-level order and each additional one."""
    entries = []
    order = result.get("order")
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    if isinstance(order, dict):
        entries.append((order, evidence, "/order"))
    extras = result.get("additional_orders")
    for i, extra in enumerate(extras if isinstance(extras, list) else []):
        if isinstance(extra, dict):
            ev = extra.get("evidence") if isinstance(extra.get("evidence"), dict) else {}
            entries.append((extra, ev, f"/additional_orders/{i}"))
    return entries


def _grounding(source: str, result: dict) -> list[ValidationError]:
    """G-1 … G-5 (R-7)."""
    errors = []
    src = ws_norm(source)
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    entries = _orders_with_pointers(result)

    def fail(code, pointer, message):
        errors.append(ValidationError(code, pointer, message, 2))

    # G-1: every quote is a substring of the source after whitespace normalisation.
    quotes = [(f"/evidence/{k}", q) for k, q in evidence.items()]
    for _order, ev, pointer in entries:
        if pointer != "/order":  # the top-level order's quotes are in `evidence` already
            quotes += [(f"{pointer}/evidence/{k}", q) for k, q in ev.items()]
    for pointer, quote in quotes:
        if isinstance(quote, str) and ws_norm(quote) not in src:
            fail("G-1", pointer, f"quote {quote!r} is not in the source text")

    for order, ev, pointer in entries:
        value, value_quote = order.get("order_value"), ev.get("order_value")
        # G-2: the value's digits are in the digits of its value quote.
        if (
            _is_number(value)
            and isinstance(value_quote, str)
            and canon_digits(value) not in digits_only(value_quote)
        ):
            fail("G-2", f"{pointer}/order_value", f"digits of {value} not in {value_quote!r}")
        # G-3: the client is contained, case-insensitively, in its client quote.
        client, client_quote = order.get("client"), ev.get("client")
        if (
            isinstance(client, str)
            and isinstance(client_quote, str)
            and ws_norm(client).casefold() not in ws_norm(client_quote).casefold()
        ):
            fail("G-3", f"{pointer}/client", f"client {client!r} not in {client_quote!r}")

    # G-4: evidence keys are exactly the non-null extracted fields.
    order = result.get("order") if isinstance(result.get("order"), dict) else None
    expected = {f for f in ("company", "announcement_date") if result.get(f) is not None}
    if order is not None:
        expected |= {f for f in ORDER_EVIDENCE_FIELDS if order.get(f) is not None}
    if set(evidence) != expected:
        fail("G-4", "/evidence", _key_diff(expected, set(evidence)))
    for extra, ev, pointer in entries:
        if pointer == "/order":
            continue
        wanted = {f for f in ADDITIONAL_EVIDENCE_FIELDS if extra.get(f) is not None}
        if set(ev) != wanted:
            fail("G-4", f"{pointer}/evidence", _key_diff(wanted, set(ev)))

    # G-5: company or a client is a stock exchange or the regulator.
    names = [("/company", result.get("company"))]
    names += [(f"{pointer}/client", o.get("client")) for o, _ev, pointer in entries]
    for pointer, name in names:
        if isinstance(name, str) and name_norm(name) in EXCHANGE_DENYLIST:
            fail("G-5", pointer, f"{name!r} is a stock exchange or regulator (FR-003)")
    return errors


def _key_diff(expected: set, actual: set) -> str:
    return (
        f"evidence keys must equal the non-null fields; missing {sorted(expected - actual)}, "
        f"extra {sorted(actual - expected)}"
    )


def expected_unstated_fields(result: dict) -> list[str]:
    """A-8 (CONFIRMED P-5): the null optional fields, in the fixed order; [] for rejected."""
    if result.get("status") == "rejected":
        return []
    fields = [f for f in ("company", "announcement_date") if result.get(f) is None]
    order = result.get("order")
    if isinstance(order, dict):
        fields += [f for f in ("order_type", "execution_period") if order.get(f) is None]
    return fields


def _consistency(result: dict) -> list[ValidationError]:
    """C-1, C-3, C-4 and C-5 (R-7). They hold by construction and guard against regressions."""
    errors = []

    def fail(code, pointer, message):
        errors.append(ValidationError(code, pointer, message, 2))

    order = result.get("order") if isinstance(result.get("order"), dict) else None
    missing = [f for f in REQUIRED_ORDER_FIELDS if order.get(f) is None] if order else []
    # C-1 (FR-011)
    if result.get("missing_fields") != missing:
        fail("C-1", "/missing_fields", f"missing_fields must be {missing}")
    # C-3 (FR-014)
    status = result.get("status")
    if order is None:
        status_ok = status in ("not_an_order", "rejected")
    else:
        status_ok = status == ("needs_clarification" if missing else "extracted")
    if not status_ok:
        fail("C-3", "/status", f"status {status!r} is inconsistent with the order (FR-014)")
    # C-4 (FR-012 rev 2, INV-10, CONFIRMED P-5)
    unstated = expected_unstated_fields(result)
    if result.get("unstated_fields") != unstated:
        fail("C-4", "/unstated_fields", f"unstated_fields must be {unstated}")
    # C-5 (FR-035 rev 3, INV-11)
    for entry, _ev, pointer in _orders_with_pointers(result):
        if "value_in_cr" not in entry:
            continue  # reported by OUT-SCHEMA
        currency, unit, value = entry.get("currency"), entry.get("unit"), entry.get("order_value")
        if currency == "INR":
            if not (_is_number(value) and unit in CRORE_MULTIPLIER):
                continue  # a broken value triplet is OUT-SCHEMA
            expected = value_in_cr(value, currency, unit)
        else:
            expected = None
        actual = entry["value_in_cr"]
        if expected is None:
            ok = actual is None
        else:
            ok = _is_number(actual) and Decimal(str(actual)) == Decimal(str(expected))
        if not ok:
            fail("C-5", f"{pointer}/value_in_cr", f"value_in_cr must be {expected} (FR-035)")
    return errors


def post_validate(source: str, result) -> list[ValidationError]:
    """Every agent check before a result is emitted (R-7): OUT-SCHEMA, OUT-DATE, G-1 … G-5,
    C-1 … C-5. All errors are collected."""
    errors = check_output(result)
    if not isinstance(result, dict):
        return errors
    return errors + _grounding(source, result) + _ranking_errors(result) + _consistency(result)
