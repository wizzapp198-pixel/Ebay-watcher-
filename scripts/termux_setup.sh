#!/data/data/com.termux/files/usr/bin/bash
# Einmalige Einrichtung in Termux. Aufruf im Repo-Ordner: bash scripts/termux_setup.sh
set -e
pkg install -y python git
pip install -r requirements.txt
if [ ! -f .env ]; then
  read -r -p "Dein ntfy-Topic: " T
  printf 'NTFY_TOPIC=%s\n' "$T" > .env
  chmod 600 .env
fi
python -m watcher --test-push --sources none || true
echo "Fertig. Start mit:  bash scripts/run_loop.sh"
