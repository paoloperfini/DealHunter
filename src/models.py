from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

@dataclass
class Offer:
    source: str
    title: str
    url: str
    price_eur: Optional[float] = None
    shipping_eur: Optional[float] = None
    availability: Optional[str] = None
    seller: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None  # new/used/etc
    extra: Dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_eur(self) -> Optional[float]:
        if self.price_eur is None:
            return None
        if self.shipping_eur is None:
            return self.price_eur
        return self.price_eur + self.shipping_eur

@dataclass
class Target:
    name: str
    keywords: List[str]
    good_price_eur: float
    great_price_eur: float
