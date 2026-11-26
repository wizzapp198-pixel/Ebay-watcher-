"""Liste der gefundenen (gemeldeten) Angebote für die Apps.

GitHub Actions schreibt neue Funde nach new_found.json; der Workflow führt sie mit
found.json auf dem Branch `watcher-data` zusammen (die Apps lesen von dort).
Aufruf: python -m watcher.found NEU.json ZIEL.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LIMIT = 300


def entry(item, watch_name: str, score, kind: str) -> dict:
    return {
        "key": item.key,
        "source": item.source,
        "title": item.title,
        "price": item.price,
        "price_negotiable": item.price_negotiable,
        "url": item.url,
        "image": item.image,
        "location": item.location,
        "watch": watch_name,
        "score": score.value,
        "reasons": score.text(),
        "kind": kind,
        "found_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def merge(existing: list[dict], new: list[dict], limit: int = LIMIT) -> list[dict]:
    """Neueste zuerst, ohne Doppelte (gleiche Quelle + ID), höchstens `limit` Einträge."""
    out, seen = [], set()
    for e in list(reversed(new)) + existing:
        if e.get("key") in seen:
            continue
        seen.add(e.get("key"))
        out.append(e)
    return out[:limit]


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data.get("found", []) if isinstance(data, dict) else []


def merge_files(new_path: Path, target: Path) -> int:
    new = json.loads(new_path.read_text(encoding="utf-8")) if new_path.exists() else []
    merged = merge(_load(target), new)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"found": merged}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(new)


if __name__ == "__main__":
    n = merge_files(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{n} neue Funde übernommen")
