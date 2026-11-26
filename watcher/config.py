"""Laden von config.yaml (global) und watches.yaml (Suchaufträge)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .models import Watch

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_EXCLUDE = ["defekt", "bastler", "ersatzteil", "kaputt", "für teile",
                   "ohne funktion", "suche", "tausche"]


@dataclass
class Settings:
    min_trust: int = 60
    send_suspicious: bool = False
    bargain_percent: float = 10.0
    max_pushes_per_run: int = 8
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    sources: dict = field(default_factory=dict)
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: Optional[str] = None
    ntfy_token: Optional[str] = None
    ebay_client_id: Optional[str] = None
    ebay_client_secret: Optional[str] = None
    db_path: str = "seen.db"
    loop_interval: int = 300
    warn_interval_minutes: int = 60

    def source_enabled(self, name: str) -> bool:
        disabled = {s.strip().lower() for s in os.environ.get("DISABLED_SOURCES", "").split(",") if s.strip()}
        if name in disabled:
            return False
        return bool(self.sources.get(name, {}).get("enabled", True))

    def source_opt(self, name: str, key: str, default=None):
        return self.sources.get(name, {}).get(key, default)


def load_dotenv(path: Path) -> None:
    """Minimaler .env-Leser (KEY=VALUE), überschreibt keine gesetzten Variablen."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _num(v):
    if v in (None, "", "None"):
        return None
    return float(str(v).replace(",", "."))


def parse_watch(d: dict) -> Watch:
    srcs = d.get("sources") or ["ebay", "kleinanzeigen"]
    if isinstance(srcs, str):
        srcs = [s.strip() for s in srcs.split(",")]
    excl = d.get("exclude") or []
    if isinstance(excl, str):
        excl = [s.strip() for s in excl.split(",") if s.strip()]
    return Watch(
        name=str(d["name"]),
        query=str(d["query"]),
        sources=[s.lower() for s in srcs],
        min_price=_num(d.get("min_price")),
        max_price=_num(d.get("max_price")),
        condition=str(d.get("condition") or "egal").lower(),
        buying=str(d.get("buying") or "egal").lower(),
        plz=str(d["plz"]) if d.get("plz") else None,
        radius=int(d["radius"]) if d.get("radius") else None,
        shipping_only=bool(d.get("shipping_only", False)),
        exclude=[e.lower() for e in excl],
        ref_price=_num(d.get("ref_price")),
        min_trust=int(d["min_trust"]) if d.get("min_trust") not in (None, "") else None,
        send_suspicious=d.get("send_suspicious"),
        active=bool(d.get("active", True)),
    )


def load_watches(path: Path) -> list[Watch]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [parse_watch(w) for w in (data.get("watches") or [])]


def load_settings(path: Path) -> Settings:
    data = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    s = Settings()
    for k in ("min_trust", "send_suspicious", "bargain_percent", "max_pushes_per_run",
              "ntfy_server", "db_path", "loop_interval", "warn_interval_minutes"):
        if k in data:
            setattr(s, k, data[k])
    if "exclude" in data:
        s.exclude = [e.lower() for e in data["exclude"] or []]
    s.sources = data.get("sources") or {}
    s.ntfy_topic = os.environ.get("NTFY_TOPIC") or None
    s.ntfy_token = os.environ.get("NTFY_TOKEN") or None
    s.ntfy_server = os.environ.get("NTFY_SERVER") or s.ntfy_server
    s.ebay_client_id = os.environ.get("EBAY_CLIENT_ID") or None
    s.ebay_client_secret = os.environ.get("EBAY_CLIENT_SECRET") or None
    s.db_path = os.environ.get("WATCHER_DB") or s.db_path
    return s
