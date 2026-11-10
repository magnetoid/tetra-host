"""Freeze the public HTTP contract (paths, methods, operation ids, parameters, schemas).

The `/api/v1` router is being split into per-plugin routers (roadmap phase 1). Moving a
handler must not change what clients see, so every route's shape is compared against a
committed snapshot. An intentional contract change regenerates it:

    UPDATE_SNAPSHOTS=1 pytest tests/test_openapi_snapshot.py
"""

import json
import os
from pathlib import Path

from app.main import app

SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi_routes.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _schema_ref(node: dict | None) -> str | None:
    if not node:
        return None
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    if node.get("type") == "array":
        inner = _schema_ref(node.get("items"))
        return f"list[{inner}]" if inner else "array"
    for key in ("anyOf", "oneOf", "allOf"):
        if key in node:
            return "|".join(sorted(str(_schema_ref(n)) for n in node[key]))
    return node.get("type")


def _body_ref(content: dict | None) -> str | None:
    if not content:
        return None
    media = content.get("application/json") or next(iter(content.values()), {})
    return _schema_ref(media.get("schema"))


def _contract() -> dict[str, dict]:
    spec = app.openapi()
    routes: dict[str, dict] = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method not in HTTP_METHODS:
                continue
            responses = op.get("responses", {})
            success = next(
                (responses[code] for code in sorted(responses) if code.startswith("2")), {}
            )
            routes[f"{method.upper()} {path}"] = {
                "operationId": op.get("operationId"),
                "parameters": sorted(
                    f"{p['in']}:{p['name']}{'!' if p.get('required') else ''}"
                    for p in op.get("parameters", [])
                ),
                "request": _body_ref(op.get("requestBody", {}).get("content")),
                "response": _body_ref(success.get("content")),
            }
    return dict(sorted(routes.items()))


def test_openapi_contract_matches_snapshot():
    current = _contract()
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=2) + "\n")
    assert SNAPSHOT.exists(), "No snapshot yet; generate it with UPDATE_SNAPSHOTS=1."
    expected = json.loads(SNAPSHOT.read_text())

    missing = sorted(set(expected) - set(current))
    added = sorted(set(current) - set(expected))
    changed = sorted(k for k in set(expected) & set(current) if expected[k] != current[k])
    assert not (missing or added or changed), (
        "HTTP contract drifted from tests/snapshots/openapi_routes.json\n"
        f"missing: {missing}\nadded: {added}\nchanged: {changed}\n"
        "If intentional, rerun with UPDATE_SNAPSHOTS=1."
    )
