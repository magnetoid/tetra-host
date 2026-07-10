"""Minimal standard 5-field cron matcher (no dependency).

Supports ``minute hour day-of-month month day-of-week`` with ``*``, ``*/step``, ``a-b`` ranges,
and ``a,b,c`` lists per field. Day-of-week is cron-style (0 or 7 = Sunday). Deliberately small —
enough to schedule HTTP jobs at minute resolution; not a full Vixie-cron implementation.
"""

from datetime import datetime


def _match_field(spec: str, value: int) -> bool:
    spec = spec.strip()
    if spec == "*":
        return True
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*/"):
            try:
                step = int(part[2:])
            except ValueError:
                continue
            if step > 0 and value % step == 0:
                return True
        elif "-" in part:
            a, _, b = part.partition("-")
            try:
                if int(a) <= value <= int(b):
                    return True
            except ValueError:
                continue
        elif part.isdigit():
            if int(part) == value:
                return True
    return False


def cron_matches(expr: str, when: datetime) -> bool:
    """True when ``expr`` fires at ``when`` (minute resolution)."""
    fields = expr.split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    cron_dow = when.isoweekday() % 7  # Python: Mon=1..Sun=7 → cron: Sun=0..Sat=6
    # Accept both 0 and 7 for Sunday by normalising 7→0 in the spec.
    dow = dow.replace("7", "0") if cron_dow == 0 else dow
    return (
        _match_field(minute, when.minute)
        and _match_field(hour, when.hour)
        and _match_field(dom, when.day)
        and _match_field(month, when.month)
        and _match_field(dow, cron_dow)
    )


def is_valid_cron(expr: str) -> bool:
    """Cheap validity check for user input (5 fields, tokens parse)."""
    fields = expr.split()
    if len(fields) != 5:
        return False
    for field in fields:
        for part in field.split(","):
            part = part.strip()
            if part == "*" or part == "":
                continue
            token = part[2:] if part.startswith("*/") else part
            token = token.replace("-", " ").replace("/", " ")
            if not all(t.isdigit() for t in token.split() if t):
                return False
    return True


__all__ = ["cron_matches", "is_valid_cron"]
