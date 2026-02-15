from __future__ import annotations
import time, requests, json
from bs4 import BeautifulSoup
from typing import List, Optional, Iterable
from ..models import Offer
from ..utils import parse_price_eur

def _iter_jsonld_objects(data) -> Iterable[dict]:
    if isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for n in graph:
                if isinstance(n, dict):
                    yield n
        yield data
    elif isinstance(data, list):
        for item in data:
            yield from _iter_jsonld_objects(item)

def _prices_from_offer_dict(o: dict) -> List[float]:
    out: List[float] = []
    for key in ("lowPrice", "price", "highPrice"):
        if key not in o:
            continue
        v = o.get(key)
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            p = parse_price_eur(v)
            if p is not None:
                out.append(p)
    return out

def _extract_prices_from_jsonld(soup: BeautifulSoup) -> List[float]:
    prices: List[float] = []
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for obj in _iter_jsonld_objects(data):
            if not isinstance(obj, dict):
                continue
            offers = obj.get("offers")
            if isinstance(offers, dict):
                prices.extend(_prices_from_offer_dict(offers))
            elif isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict):
                        prices.extend(_prices_from_offer_dict(o))
            # Sometimes offer-like fields exist at the top level
            prices.extend(_prices_from_offer_dict(obj))
    return [p for p in prices if p and p > 0]

def _extract_meta_price(soup: BeautifulSoup) -> Optional[float]:
    for sel, attr in [
        ('meta[property="product:price:amount"]', "content"),
        ('meta[property="og:price:amount"]', "content"),
        ('meta[itemprop="price"]', "content"),
    ]:
        tag = soup.select_one(sel)
        if tag and tag.get(attr):
            p = parse_price_eur(tag.get(attr))
            if p is not None:
                return p
    return None

def fetch_idealo_list(url: str, user_agent: str, delay: float = 1.0) -> List[Offer]:
    headers = {"User-Agent": user_agent}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    time.sleep(delay)
    soup = BeautifulSoup(r.text, "lxml")
    offers: List[Offer] = []

    h1 = soup.select_one("h1")
    page_title = " ".join(h1.get_text(" ", strip=True).split()) if h1 else "Idealo item"

    prices = _extract_prices_from_jsonld(soup)
    meta = _extract_meta_price(soup)
    if meta is not None:
        prices.append(meta)

    if not prices:
        # Fallback (less reliable)
        text = soup.get_text(" ", strip=True)
        p = parse_price_eur(text)
        if p is not None:
            prices.append(p)

    if prices:
        offers.append(Offer(source="idealo", title=page_title, url=url, price_eur=min(prices), condition="new"))
    return offers
