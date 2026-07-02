"""Parse `docker stats` output into normalized per-container compute samples.

`docker stats --format '{{json .}}'` emits human-formatted strings (e.g. CPU "12.34%",
memory "45.7MiB / 512MiB", net "1.2kB / 3.4MB"). These pure helpers turn them into numbers
the console/CLI can chart — kept I/O-free so they're trivially unit-testable.
"""

import re
from dataclasses import dataclass

_SIZE = re.compile(r"^\s*([0-9.]+)\s*([A-Za-z]*)\s*$")
_UNIT_BYTES = {
    "": 1.0, "b": 1.0,
    "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
    "kib": 1024.0, "mib": 1024.0**2, "gib": 1024.0**3, "tib": 1024.0**4,
}


@dataclass(slots=True)
class ComputeSample:
    name: str
    cpu_percent: float = 0.0
    mem_used_mb: float = 0.0
    mem_limit_mb: float = 0.0
    mem_percent: float = 0.0
    net_rx_mb: float = 0.0
    net_tx_mb: float = 0.0
    pids: int = 0


def parse_size_to_bytes(text: str) -> float:
    """'45.7MiB' → bytes; '0B'/''/'--' → 0.0. Binary (MiB) and decimal (MB) both handled."""
    match = _SIZE.match(text or "")
    if not match:
        return 0.0
    value, unit = match.groups()
    try:
        return float(value) * _UNIT_BYTES.get(unit.lower(), 1.0)
    except ValueError:
        return 0.0


def _mb(text: str) -> float:
    return round(parse_size_to_bytes(text) / 1e6, 2)


def _percent(text: str) -> float:
    try:
        return round(float((text or "").strip().rstrip("%")), 2)
    except ValueError:
        return 0.0


def _split_pair(text: str) -> tuple[str, str]:
    left, _, right = (text or "").partition("/")
    return left.strip(), right.strip()


def parse_compute_samples(raw: list[dict]) -> list[ComputeSample]:
    """Normalize `docker stats` JSON rows into ComputeSample values."""
    samples: list[ComputeSample] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        used, limit = _split_pair(row.get("MemUsage", ""))
        rx, tx = _split_pair(row.get("NetIO", ""))
        try:
            pids = int(str(row.get("PIDs", "0")).strip() or 0)
        except ValueError:
            pids = 0
        samples.append(
            ComputeSample(
                name=str(row.get("Name") or row.get("Container") or row.get("ID") or ""),
                cpu_percent=_percent(row.get("CPUPerc", "")),
                mem_used_mb=_mb(used),
                mem_limit_mb=_mb(limit),
                mem_percent=_percent(row.get("MemPerc", "")),
                net_rx_mb=_mb(rx),
                net_tx_mb=_mb(tx),
                pids=pids,
            )
        )
    return samples
