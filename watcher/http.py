"""HTTP-Session mit höflichem Rate-Limit und Retry/Backoff."""
from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class SourceError(Exception):
    """Quelle temporär nicht nutzbar."""


class SourceBlocked(SourceError):
    """Quelle verweigert den Zugriff (403/429/Captcha). Wird NICHT umgangen."""


class PoliteSession:
    def __init__(self, min_delay: float = 4.0, jitter: float = 2.0, retries: int = 3,
                 backoff: float = 5.0, timeout: float = 20.0, headers: dict | None = None,
                 sleep=time.sleep):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": BROWSER_UA,
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        if headers:
            self.s.headers.update(headers)
        self.min_delay, self.jitter = min_delay, jitter
        self.retries, self.backoff, self.timeout = retries, backoff, timeout
        self._last = 0.0
        self._sleep = sleep

    def _wait(self):
        gap = self.min_delay + random.uniform(0, self.jitter)
        elapsed = time.monotonic() - self._last
        if self._last and elapsed < gap:
            self._sleep(gap - elapsed)

    def get(self, url: str, **kw) -> requests.Response:
        last_err = None
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                r = self.s.get(url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                last_err = e
                log.warning("Netzwerkfehler %s (Versuch %d): %s", url, attempt + 1, e)
            else:
                self._last = time.monotonic()
                if r.status_code in (403, 429):
                    hint = " (IP-Bereich gesperrt)" if "gesperrt" in r.text[:3000] else ""
                    raise SourceBlocked(f"HTTP {r.status_code}{hint} bei {url.split('?')[0]}")
                if r.status_code >= 500:
                    last_err = SourceError(f"HTTP {r.status_code}")
                    log.warning("Serverfehler %s bei %s", r.status_code, url)
                else:
                    return r
            self._last = time.monotonic()
            if attempt < self.retries:
                self._sleep(self.backoff * (3 ** attempt))
        raise SourceError(f"{url.split('?')[0]}: {last_err}")
