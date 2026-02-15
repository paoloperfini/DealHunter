from __future__ import annotations
import re
from typing import Optional

PRICE_RE = re.compile(r"(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?)")

def parse_price_eur(text: str) -> Optional[float]:
    if not text:
        return None
    m = PRICE_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    s = m.group(1)
    # normalize "3.263,65" or "3,263.65"
    if s.count(",") == 1 and s.count(".") >= 1:
        # assume dots are thousands, comma is decimals
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

def contains_any(hay: str, needles: list[str]) -> bool:
    h = (hay or "").lower()
    return any(n.lower() in h for n in needles)
