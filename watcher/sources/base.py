"""Basisklasse für Quellen-Adapter.

Neue Quelle ergänzen:
  1. Datei watcher/sources/<name>.py mit Klasse(Source) anlegen,
  2. search(watch) -> list[Item] implementieren (optional details(item)),
  3. in watcher/sources/__init__.py in REGISTRY eintragen.
"""
from __future__ import annotations

from ..models import Item, Watch


class Source:
    name = "base"
    label = "Basis"

    def __init__(self, settings):
        self.settings = settings

    def search(self, watch: Watch) -> list[Item]:
        raise NotImplementedError

    def details(self, item: Item) -> Item:
        """Optional: Zusatzinfos (Verkäuferprofil, Beschreibung) nachladen."""
        return item

    def configured(self) -> tuple[bool, str]:
        return True, ""
