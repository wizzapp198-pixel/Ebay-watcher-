#!/usr/bin/env bash
# Dauerbetrieb für Termux (Android), Raspberry Pi oder Heim-PC.
# Holt vor jedem Lauf die aktuellen Suchaufträge (git pull) und startet einen Durchlauf.
#   SOURCES=kleinanzeigen  -> nur Kleinanzeigen (eBay läuft dann auf GitHub)
#   SOURCES=ebay,kleinanzeigen -> alles lokal (dann GitHub-Workflow deaktivieren!)
#   INTERVAL=300           -> Sekunden zwischen Läufen
cd "$(dirname "$0")/.." || exit 1
SOURCES="${SOURCES:-kleinanzeigen}"
INTERVAL="${INTERVAL:-300}"
command -v termux-wake-lock >/dev/null && termux-wake-lock
while true; do
  git pull -q --ff-only 2>/dev/null || echo "git pull fehlgeschlagen – nutze lokale watches.yaml"
  python -m watcher --once --sources "$SOURCES" --schedule-interval "$INTERVAL"
  sleep "$INTERVAL"
done
