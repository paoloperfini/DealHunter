from __future__ import annotations
import os, json, csv
from typing import List, Optional
from ..models import Offer
from ..utils import parse_price_eur

def ingest_folder(folder: str) -> List[Offer]:
    offers: List[Offer] = []
    if not os.path.isdir(folder):
        return offers

    for fn in os.listdir(folder):
        path = os.path.join(folder, fn)
        if fn.lower().endswith(".jsonl"):
            offers.extend(_read_jsonl(path))
        elif fn.lower().endswith(".json"):
            offers.extend(_read_json(path))
        elif fn.lower().endswith(".csv"):
            offers.extend(_read_csv(path))
    return offers

def _read_jsonl(path: str) -> List[Offer]:
    out=[]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            out.append(_from_dict(json.loads(line)))
    return out

def _read_json(path: str) -> List[Offer]:
    with open(path, "r", encoding="utf-8") as f:
        data=json.load(f)
    if isinstance(data, list):
        return [_from_dict(x) for x in data]
    if isinstance(data, dict) and "items" in data:
        return [_from_dict(x) for x in data["items"]]
    return [_from_dict(data)] if isinstance(data, dict) else []

def _read_csv(path: str) -> List[Offer]:
    out=[]
    with open(path, newline="", encoding="utf-8") as f:
        r=csv.DictReader(f)
        for row in r:
            out.append(_from_dict(row))
    return out

def _from_dict(d: dict) -> Offer:
    title = d.get("title") or d.get("name") or ""
    url = d.get("url") or d.get("link") or ""
    price = d.get("price_eur")
    if price is None:
        price = parse_price_eur(str(d.get("price","") or d.get("prezzo","") or ""))
    shipping = d.get("shipping_eur")
    if shipping is None:
        shipping = parse_price_eur(str(d.get("shipping","") or d.get("spedizione","") or "")) if d.get("shipping") or d.get("spedizione") else None
    cond = d.get("condition") or d.get("condizione")
    seller = d.get("seller")
    location = d.get("location") or d.get("citta") or d.get("city")
    extra = dict(d)
    extra.pop("title", None); extra.pop("url", None)
    return Offer(
        source="subito_ingest",
        title=title,
        url=url,
        price_eur=price,
        shipping_eur=shipping,
        condition=cond,
        seller=seller,
        location=location,
        extra=extra
    )
