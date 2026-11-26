"""Diagnose: prüft drei Beispiel-Angebote mit der eingestellten KI (python -m watcher.ai_probe)."""
import logging
from pathlib import Path

from .ai import AIChecker
from .config import ROOT, load_settings
from .models import Item, Watch

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
settings = load_settings(Path(ROOT / "config.yaml"))
ai = AIChecker(settings)
print("KI-Anbieter:", ai.provider, "Modell:", ai.model)
if not ai.enabled:
    print("Kein KI-Key gesetzt – nichts zu testen.")
    raise SystemExit(0)
w = Watch(name="Fahrrad", query="fahrrad", max_price=1200)
items = [
    Item(id="1", source="kleinanzeigen", title="Schwalbe Marathon Plus Fahrrad Trekking 37-622", url="u", price=29,
         attributes={"Art": "Zubehör"}, description="Original Schwalbe Marathon Reifen, brandneu"),
    Item(id="2", source="kleinanzeigen", title="Puky Spielzeug Laufrad Holz", url="u", price=5,
         description="Kinderspielzeug, Laufrad aus Holz für Puppen"),
    Item(id="3", source="kleinanzeigen", title="Damenrad 28 Zoll Kalkhoff 7 Gang", url="u", price=180,
         description="Gepflegtes Damenrad, fahrbereit, neue Bremsen"),
    Item(id="4", source="kleinanzeigen", title="SUCHE Fahrrad 28 Zoll", url="u", price=None,
         description="Suche günstiges Fahrrad für den Arbeitsweg"),
]
for it, v in zip(items, ai.check_many(items, w).values()):
    print(f"{it.title[:45]:45} -> {'OK' if v and v.ok else ('RAUS' if v else 'ungeprüft')}: {v.reason if v else ''}")
