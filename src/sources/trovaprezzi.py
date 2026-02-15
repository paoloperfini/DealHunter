from __future__ import annotations
import time, requests
from bs4 import BeautifulSoup
from typing import List
from ..models import Offer
from ..utils import parse_price_eur

def fetch_trovaprezzi_list(url: str, user_agent: str, delay: float = 1.0) -> List[Offer]:
    headers = {"User-Agent": user_agent}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    time.sleep(delay)
    soup = BeautifulSoup(r.text, "lxml")

    offers: List[Offer] = []
    # Trovaprezzi pages vary; we try a generic extraction for product cards/rows.
    for a in soup.select("a[href]"):
        href = a.get("href","")
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or len(title) < 8:
            continue
        if "trovaprezzi.it" not in href and not href.startswith("/"):
            continue
        full = href if href.startswith("http") else "https://www.trovaprezzi.it" + href
        # try nearby price
        parent = a.parent
        price = None
        for _ in range(3):
            if parent is None: break
            txt = parent.get_text(" ", strip=True)
            if "€" in txt:
                price = parse_price_eur(txt)
                if price: break
            parent = parent.parent
        if price is None:
            continue
        offers.append(Offer(source="trovaprezzi", title=title, url=full, price_eur=price, condition="new"))
    # de-dup by url
    uniq = {}
    for o in offers:
        uniq[o.url] = o
    return list(uniq.values())
