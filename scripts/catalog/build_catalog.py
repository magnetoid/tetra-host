"""Build Tetra Host's app catalog (app/catalog/templates.json) from a template export.

The catalog is ours and ships in the repo: the panel never fetches templates or logos
at runtime. This maintainer tool turns a third-party template export (see
app/catalog/NOTICE.md for provenance and licence) into our format:

    python scripts/catalog/build_catalog.py <export.json> [--logos <dir>]

Each entry keeps its compose file (base64) and gets a plain logo filename that the
console serves from apps/web/public/catalog/logos/. With --logos, the logo files are
copied there from <dir>. Templates whose logo is missing keep an empty logo.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "app" / "catalog" / "templates.json"
LOGO_DIR = ROOT / "apps" / "web" / "public" / "catalog" / "logos"


def convert(slug: str, raw: dict, logos: set[str] | None) -> dict:
    logo = Path(str(raw.get("logo") or "")).name
    if logos is not None and logo not in logos:
        logo = ""
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    return {
        "slug": slug,
        "name": str(raw.get("name") or slug),
        "description": str(raw.get("slogan") or raw.get("description") or ""),
        "category": str(raw.get("category") or "other"),
        "tags": [str(t) for t in tags],
        "logo": logo,
        "port": str(raw.get("port") or ""),
        "documentation": str(raw.get("documentation") or ""),
        "compose": str(raw.get("compose") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", type=Path)
    parser.add_argument("--logos", type=Path, help="directory holding the logo files")
    args = parser.parse_args()

    source = json.loads(args.export.read_text())
    logos = None
    if args.logos:
        LOGO_DIR.mkdir(parents=True, exist_ok=True)
        logos = set()
        for file in sorted(args.logos.iterdir()):
            if file.is_file() and file.stat().st_size > 0:
                shutil.copyfile(file, LOGO_DIR / file.name)
                logos.add(file.name)

    templates = [
        convert(slug, raw, logos)
        for slug, raw in source.items()
        if isinstance(raw, dict) and raw.get("compose")
    ]
    templates.sort(key=lambda t: t["name"].lower())
    CATALOG.write_text(json.dumps({"version": 1, "templates": templates}, indent=1) + "\n")
    print(f"{len(templates)} templates → {CATALOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
