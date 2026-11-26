"""Push über ntfy (JSON-Publish, UTF-8-sicher)."""
from __future__ import annotations

import logging

import requests

from .models import SOURCE_LABELS, Item

log = logging.getLogger(__name__)


class PushError(Exception):
    pass


class Notifier:
    def __init__(self, server: str, topic: str | None, token: str | None = None,
                 session: requests.Session | None = None):
        self.server = server.rstrip("/")
        self.topic = topic
        self.token = token
        self.http = session or requests.Session()

    def send(self, title: str, message: str, priority: int = 3, tags: list[str] | None = None,
             click: str | None = None, image: str | None = None) -> None:
        if not self.topic:
            raise PushError("NTFY_TOPIC fehlt")
        payload = {"topic": self.topic, "title": title[:250], "message": message[:3900],
                   "priority": int(priority), "tags": tags or []}
        if click:
            payload["click"] = click
            payload["actions"] = [{"action": "view", "label": "Angebot öffnen", "url": click}]
        if image:
            payload["attach"] = image
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            r = self.http.post(self.server, json=payload, headers=headers, timeout=15)
        except requests.RequestException as e:
            raise PushError(str(e)) from e
        if r.status_code >= 300:
            raise PushError(f"ntfy HTTP {r.status_code}: {r.text[:200]}")


def format_price(item: Item) -> str:
    if item.price is None:
        return "Preis k. A." + (" (VB)" if item.price_negotiable else "")
    p = f"{item.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if p.endswith(",00"):
        p = p[:-3]
    return f"{p} €" + (" VB" if item.price_negotiable else "") + (" (Gebot)" if item.is_auction else "")


def build_push(item: Item, watch_name: str, score, kind: str) -> dict:
    """kind: normal | bargain | suspicious"""
    src = SOURCE_LABELS.get(item.source, item.source)
    prefix = {"bargain": "🔥 ", "suspicious": "⚠️ "}.get(kind, "")
    title = f"{prefix}[{src}] {format_price(item)} – {item.title}"
    lines = [
        f"Suchauftrag: {watch_name}",
        f"Vertrauen: {score.value}/100 – {score.text()}",
    ]
    if item.location:
        lines.append(f"Ort: {item.location}")
    if item.condition:
        lines.append(f"Zustand: {item.condition}")
    if item.seller and item.seller.name:
        lines.append(f"Verkäufer: {item.seller.name}")
    prio = {"bargain": 5, "suspicious": 2}.get(kind, 3)
    tags = [{"ebay": "shopping_cart", "kleinanzeigen": "green_circle"}.get(item.source, "bell")]
    if kind == "bargain":
        tags.append("fire")
    if kind == "suspicious":
        tags.append("warning")
    return dict(title=title, message="\n".join(lines), priority=prio, tags=tags,
                click=item.url, image=item.image)
