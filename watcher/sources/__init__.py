from .base import Source
from .ebay import EbaySource
from .kleinanzeigen import KleinanzeigenSource

# Neue Quellen hier eintragen: name -> Klasse
REGISTRY = {
    "ebay": EbaySource,
    "kleinanzeigen": KleinanzeigenSource,
}

__all__ = ["Source", "REGISTRY", "EbaySource", "KleinanzeigenSource"]
