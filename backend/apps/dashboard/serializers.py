"""snake_case -> camelCase, once, on the way out.

The aggregations compute in Python's spelling and the React types are written
in JavaScript's. Renaming here rather than at either end means neither side has
to hold both spellings in its head: `metrics.py` never writes `marginPct`, and
`api-types.ts` never sees `margin_pct`.

The rename is mechanical, which is the point — a payload builder cannot forget
a field, because it never lists them.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in rest)


def camelize(value: Any) -> Any:
    """Recursively rename dict keys, leaving values alone.

    Keys starting with "_" are dropped: `metrics` uses that prefix for the
    running totals it needs while accumulating and does not mean to publish.
    """
    if isinstance(value, dict):
        return {camel(k): camelize(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, (list, tuple)):
        return [camelize(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
