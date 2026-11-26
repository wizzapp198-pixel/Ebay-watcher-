# eBay- & Kleinanzeigen-Watcher

Sucht laufend nach **neuen** Angeboten auf eBay.de und Kleinanzeigen.de, prüft jedes auf
Seriosität (Score 0–100 mit Begründung) und schickt gute Treffer als Push aufs Handy (ntfy).
Alles wird vom Handy aus eingerichtet und bedient – Suchaufträge legst du über ein Formular an,
YAML musst du nie anfassen.

| Push | Bedeutung |
|---|---|
| `[eBay] 289 € – iPhone 13 …` | normaler Treffer (Priorität normal) |
| `🔥 [Kleinanzeigen] …` | Schnäppchen: ≥ 10 % unter Referenzpreis, Vertrauen gut (Priorität hoch) |
| `⚠️ [eBay] …` | verdächtig, nur wenn „Verdächtige trotzdem senden“ an ist (Priorität niedrig) |
| `⚠️ Watcher: Kleinanzeigen gestört` | Quelle fällt aus/blockt (max. 1× pro Stunde) |

Tippen auf den Push öffnet das Angebot. Im Text: Suchauftrag, Vertrauen + Gründe, Ort, Zustand, Verkäufer.

---

## Einrichtung vom Handy (ca. 15 Min.)

### 1. ntfy-App (2 Min.)
1. App **ntfy** aus Play Store / App Store installieren.
2. **+** → „Subscribe to topic“ → einen langen, zufälligen Namen ausdenken, z. B. `watcher-k7f3q9xa2m`.
   Wer den Namen kennt, kann deine Pushes lesen – also nicht erratbar wählen. Merken!

### 2. eBay-Developer-Keys (8 Min.)
1. Im Handy-Browser <https://developer.ebay.com> → **Register** (mit deinem eBay-Konto anmelden geht nicht – eigener Developer-Account, kostenlos).
2. Nach Bestätigung: **Hi <Name> → Application Keys**. Einen App-Namen eintragen, bei **Production** auf **Create a keyset**.
3. eBay verlangt dann die Angabe zu **Marketplace Account Deletion**. Da dieses Tool keine eBay-Nutzerdaten speichert:
   Schalter **„Not persisting eBay data“ / „I do not persist eBay data“** (Befreiung/Exemption) aktivieren,
   Grund auswählen (z. B. „I do not store eBay user data“) → **Submit**. Danach ist das Production-Keyset aktiv.
4. Notieren: **App ID (Client ID)** und **Cert ID (Client Secret)** aus der Zeile *Production*.

### 3. Repo und Secrets in GitHub (4 Min.)
Im Handy-Browser (nicht in der GitHub-App, dort fehlen die Einstellungen) dein Repo öffnen:
`https://github.com/wizzapp198-pixel/Ebay-watcher-`

**Sichtbarkeit (du wolltest privat):** **Settings** (oben in der Leiste, ggf. nach rechts wischen)
→ ganz unten *Danger Zone* → **Change visibility** → **Make private** → bestätigen.

**Secrets:** **Settings → Secrets and variables → Actions → New repository secret**, drei Stück anlegen:

| Name (genau so tippen) | Wert |
|---|---|
| `EBAY_CLIENT_ID` | App ID aus Schritt 2 |
| `EBAY_CLIENT_SECRET` | Cert ID aus Schritt 2 |
| `NTFY_TOPIC` | dein Topic-Name aus Schritt 1 |

Optional: `NTFY_TOKEN`, falls du einen geschützten ntfy-Server/Account nutzt.

### 4. Erster Start + Test-Push (1 Min.)
**Actions** → links **Watcher** → **Run workflow** → Haken bei **Test-Push senden** → grüner **Run workflow**-Knopf.
Nach ca. 1 Min. kommt „✅ Watcher-Test: Push funktioniert“ aufs Handy.
Falls Actions noch nicht aktiv ist: einmal **„I understand my workflows, go ahead and enable them“** tippen.

Danach läuft der Watcher automatisch **alle 30 Minuten**.
Hinweis: GitHub startet geplante Läufe oft **einige Minuten verspätet** (manchmal 10–20 Min.), das ist normal.

---

## Suchaufträge anlegen, ändern, löschen

* **Anlegen/Ändern:** Repo → **Issues → New issue → „➕ Suchauftrag anlegen / ändern“** → Felder ausfüllen → **Create**.
  Gleicher Name = bestehender Auftrag wird überschrieben (z. B. zum Pausieren: Haken „pausieren“).
* **Löschen:** **New issue → „🗑️ Suchauftrag löschen“** → Namen eintragen.
* **Liste ansehen:** Datei **WATCHES.md** im Repo.

Der Bot antwortet im Issue mit ✅ oder ❌ (mit Grund) und schließt es. Nur du (Repo-Besitzer) kannst Aufträge ändern.

**Felder:** Suchbegriff, Quellen (eBay/Kleinanzeigen/beide), Min-/Max-Preis, **Referenzpreis** (üblicher Marktpreis –
wichtig für Schnäppchen- und Betrugserkennung), Zustand, eBay-Kaufart (Sofort-Kaufen/Auktion/egal),
Kleinanzeigen-PLZ + Umkreis (Gräfenhainichen 06773, Bitterfeld-Wolfen 06749), „nur mit Versand“,
eigene Ausschlusswörter, Mindest-Vertrauen, „verdächtige trotzdem senden“.

**Kein Push-Spam:** Beim ersten Lauf eines neuen oder geänderten Suchauftrags werden vorhandene Angebote nur gemerkt.
Erst danach kommen neue. Pro Lauf max. 8 Pushes (Rest im nächsten Lauf).

Globale Ausschlusswörter (defekt, Bastler, Ersatzteil, kaputt, für Teile, iCloud, suche, tausche …) stehen in `config.yaml`.

---

## Seriositäts-Score

Start 70 Punkte, dann:

* **eBay:** Bewertungsquote (≥ 99,5 % +10 … < 90 % −30), Anzahl Bewertungen (< 5 = neuer Account −25, < 20 −15, ≥ 1000 +10),
  Standort Ausland (−5 Nachbarland, −20 sonst). Preis < 50 % vom Referenzpreis −40 (nur Sofort-Kaufen; Auktionen starten oft billig).
* **Kleinanzeigen** (Profil wird nur für Angebote geladen, die sonst gepusht würden): „Aktiv seit“ (< 30 Tage −25, < 6 Monate −10,
  > 3 Jahre +10), Badges (TOP Zufriedenheit +10, Zuverlässig/Freundlich +5), privat/gewerblich, Anzahl Anzeigen,
  „Direkt kaufen“/Sicher bezahlen +10, Preis vs. Referenz.
* **Beide:** Starke Betrugs-Wörter (WhatsApp, Telegram, PayPal Freunde, Western Union, Krypto, Zahlung außerhalb,
  Anzahlung, Treuhand, Kontakt per Mail/E-Mail-Adresse) → Score **immer unter** deinem Mindest-Vertrauen.
  Weiche Hinweise (Vorkasse, nur Überweisung, Telefonnummer im Text) −10.

Unter Mindest-Vertrauen (Standard 60) wird nicht gepusht – außer „Verdächtige trotzdem senden“ ist an.

---

## KI-Prüfung (optional, empfohlen)

Filter und Ausschlusswörter fangen nicht alles ab: Spielzeugrad statt Fahrrad, Komplett-PC statt
Grafikkarte, „Suche RX 9070 XT“ oder „Ankauf aller Grafikkarten“. Deshalb kann Claude (KI von Anthropic)
jedes Angebot prüfen, **bevor** es gepusht wird:

* Ist es **genau der gesuchte Artikel** (kein Zubehör, kein Spielzeug, kein anderes Modell, kein Komplettgerät)?
* Ist es ein **Verkauf** (kein Gesuch, kein Ankauf, keine Dienstleistung)?

Die Begründung steht im Push („KI ✓ …“). Pro Suchauftrag kannst du im Feld **„Genauer Wunsch“** beschreiben,
was du genau willst, z. B. *„Nur die einzelne Karte RX 9070 XT, nicht die non-XT, kein Komplett-PC“*.
Auch ohne KI werden Kleinanzeigen-Gesuche (laut Anzeigentyp) und Titel mit „Ankauf“/„Gesuch“/„Suche“ aussortiert.

**Einrichten:**
1. <https://console.anthropic.com> → Konto anlegen → **Billing**: Guthaben aufladen (Prepaid, kein Abo).
2. **API Keys → Create Key** → kopieren.
3. GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
   Name `ANTHROPIC_API_KEY`, Wert = der Key.

Ohne Key läuft alles wie bisher, nur ohne KI-Prüfung.

**Kosten:** Geprüft werden nur Angebote, die alle anderen Filter bestanden haben (max. 25 pro Lauf).
Standard ist das genaueste Modell `claude-opus-5-5` (ca. 1 Cent pro Prüfung). Wer sparen will,
stellt in `config.yaml` bei `ai: model:` auf `claude-haiku-5-5` um (Bruchteil eines Cents, etwas ungenauer).
In der Anthropic-Console kannst du ein monatliches Ausgabenlimit setzen.

---

## Kleinanzeigen: Cloud vs. Zuhause

Kleinanzeigen hat **keine offizielle API**; der Watcher liest die öffentlichen Suchseiten (neueste zuerst) mit
mind. 4–6 s Abstand pro Anfrage, Retry mit Backoff, ohne Login. **Sperren oder Captchas werden nicht umgangen.**

**Getestet am 26.11.2026:** Von **GitHub Actions aus funktioniert Kleinanzeigen** (Testsuche: 27 Treffer korrekt gelesen).
Von einem anderen Cloud-Server kam dagegen „IP-Bereich vorübergehend gesperrt“ (HTTP 403) – Kleinanzeigen sperrt
also manche Cloud-IP-Bereiche, und das kann sich jederzeit auch für GitHub ändern.
Der Watcher erkennt eine Sperre, schickt höchstens 1× pro Stunde eine Warnung, und **eBay läuft normal weiter**.

**Wenn die Warnung regelmäßig kommt:** Kleinanzeigen in GitHub abschalten und zu Hause laufen lassen.

1. GitHub (Browser): **Settings → Secrets and variables → Actions → Reiter „Variables“ → New repository variable**:
   Name `DISABLED_SOURCES`, Wert `kleinanzeigen`.
2. **Android mit Termux** (F-Droid-Version von Termux installieren, nicht Play Store):
   ```
   pkg install -y git gh
   gh auth login            # GitHub.com → HTTPS → Login with a web browser
   gh repo clone wizzapp198-pixel/Ebay-watcher-
   cd Ebay-watcher-
   bash scripts/termux_setup.sh      # fragt nach deinem ntfy-Topic, schickt Test-Push
   bash scripts/run_loop.sh          # läuft dauerhaft, alle 5 Min., nur Kleinanzeigen
   ```
   In Android für Termux **Akku-Optimierung deaktivieren**, sonst stoppt Android den Prozess.
   Optional „Termux:Boot“ für Autostart.
3. **Raspberry Pi / Heim-PC:** gleiche Befehle (statt `pkg` → `sudo apt install python3-pip git gh`),
   dann `SOURCES=kleinanzeigen bash scripts/run_loop.sh` (z. B. in `tmux` oder als systemd-Dienst).

Neue Suchaufträge aus den Issues holt der Dauerbetrieb automatisch per `git pull` vor jedem Lauf.
Läuft dort **alles** (`SOURCES=ebay,kleinanzeigen`), dann eBay-Keys in `.env` eintragen und den GitHub-Workflow
deaktivieren (Actions → Watcher → ⋯ → Disable workflow), sonst kommen Pushes doppelt.

---

## Steuerung per App (iPhone) und Web-App

Beide Apps zeigen im Tab **Funde** alle gemeldeten Angebote (letzte 300, mit Bild, Preis, Vertrauen und
Begründung; antippen öffnet das Angebot) – auch wenn eine Push-Nachricht nicht ankommt. Gespeichert werden sie
im Repo auf dem Branch `watcher-data` (Datei `found.json`).

**Sortieren wie bei Tinder:** Unter „Funde → Neu“ liegt jedes Angebot als Karte.
**Nach links wischen = behalten** (landet unter „Behalten“), **nach rechts wischen = löschen** (verschwindet).
Antippen öffnet das Angebot, ↶ macht den letzten Schritt rückgängig. Die Sortierung wird zwischen iPhone-App und
Web-App abgeglichen (Datei `decisions.json` auf `watcher-data`), dafür braucht der Token das Recht
**Contents: Read and write**. Ohne dieses Recht wird nur auf dem jeweiligen Gerät gespeichert.

Außerdem können beide: Suchaufträge ansehen, anlegen, ändern, pausieren und löschen, **Jetzt suchen**,
**Test-Push** und die letzten Läufe anzeigen. Änderungen laufen intern über dasselbe Issue-Formular
(gleiche Prüfung, gleicher Bot), die App zeigt dir die Antwort des Bots direkt an.

### Zugangsschlüssel (Token) – einmalig, für beide Apps
1. Im Handy-Browser: <https://github.com/settings/personal-access-tokens/new>
2. Name: `Watcher App`, Expiration: 1 Jahr (oder „No expiration“).
3. **Repository access → Only select repositories →** `Ebay-watcher-`
4. **Permissions → Repository permissions:**
   **Actions:** Read and write · **Contents:** Read and write · **Issues:** Read and write (Metadata stellt GitHub automatisch ein).
5. **Generate token**, kopieren und in der App einfügen. Nicht im Chat oder irgendwo anders speichern.

Der Token wird in der iOS-App im Schlüsselbund gespeichert, in der Web-App nur im Browser dieses Geräts,
und nur an `api.github.com` gesendet.

### iOS-App (.ipa zum Sideloaden)
* Download: Repo → **Releases → „Watcher iOS-App (neuester Build)“ → `Watcher.ipa`**
  (wird bei jeder Änderung unter `ios/` automatisch neu gebaut).
* Die IPA ist unsigniert. AltStore, SideStore, Sideloadly, Feather & Co. signieren sie beim Installieren mit deiner Apple-ID.
* Mit kostenloser Apple-ID läuft die Signatur nach **7 Tagen** ab → in AltStore/SideStore „Refresh“.
  Vergessen? Einfach die Web-App nutzen, die läuft immer.

### Web-App (läuft immer, kein Refresh nötig)
* Liegt in `webapp/`, gehostet über GitHub Pages im öffentlichen Mini-Repo `watcher-app`
  (enthält nur den App-Code – keine Suchaufträge, keine Keys).
* In Safari öffnen → **Teilen → Zum Home-Bildschirm**: sieht dann aus wie eine App.

---

## Limits & Kosten

* **eBay Browse API:** ca. 5000 Aufrufe/Tag. Pro Lauf 1 Aufruf je eBay-Suchauftrag (+1 Token).
  Alle 30 Min. = 48 Läufe/Tag → **10 Aufträge ≈ 480 Aufrufe/Tag**, bis ~80 Aufträge unkritisch.
  Dauerbetrieb alle 5 Min. = 288 Läufe → max. ~13 eBay-Aufträge. Der Log zeigt die Hochrechnung bei jedem Lauf.
* **GitHub Actions (privates Repo):** 2000 Gratis-Minuten/Monat, jeder Lauf zählt aufgerundet als ≥ 1 Minute.
  Ein iOS-App-Build (macOS, zählt 10-fach) kostet ca. 10–20 Minuten und läuft nur bei Änderungen unter `ios/`.
  48 Läufe/Tag × 30 Tage ≈ 1440 Min. → passt. Nicht schneller als 30 Min. stellen (20 Min. ≈ 2160 Min. = zu viel).
  Bei einem **öffentlichen** Repo sind Minuten unbegrenzt – dann kannst du in `.github/workflows/watch.yml`
  `*/30` auf `*/5` ändern (Suchliste wäre dann öffentlich sichtbar, Keys bleiben geheim).

---

## Technik

```
watcher/
  sources/base.py           Adapter-Basisklasse: search(watch), optional details(item)
  sources/ebay.py           Browse API, OAuth client_credentials, EBAY_DE, sort=newlyListed
  sources/kleinanzeigen.py  HTML-Parser Such- und Anzeigenseite
  scoring.py  notify.py (ntfy JSON)  store.py (SQLite)  runner.py  __main__.py
scripts/manage_watches.py   Issue-Formular → watches.yaml + WATCHES.md
.github/workflows/          watch.yml (Cron + manuell), manage-watches.yml, tests.yml
tests/                      pytest ohne Netzwerk, gespeicherte Kleinanzeigen-HTML-Seiten
```

Neue Quelle: Klasse in `watcher/sources/<name>.py` von `Source` ableiten, in `watcher/sources/__init__.py` eintragen.

Lokal: `.env.example` → `.env`, dann `python -m watcher --once`, `--loop`, `--test-push`, `--sources kleinanzeigen`.
Zustand (`seen.db`) liegt in GitHub im Actions-Cache. Tests: `python -m pytest`.
