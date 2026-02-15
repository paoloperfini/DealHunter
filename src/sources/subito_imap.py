from __future__ import annotations
from typing import List, Dict, Any
from imapclient import IMAPClient
import email
from email.header import decode_header
from ..models import Offer
from ..utils import parse_price_eur

def _decode(s):
    if not s:
        return ""
    parts = decode_header(s)
    out=[]
    for p, enc in parts:
        if isinstance(p, bytes):
            out.append(p.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(p)
    return "".join(out)

def fetch_subito_alerts_imap(cfg: Dict[str, Any]) -> List[Offer]:
    im = cfg["imap"]
    host, port = im["host"], int(im.get("port", 993))
    user = _getenv(im["user_env"])
    pwd = _getenv(im["password_env"])
    folder = im.get("folder","INBOX")
    search_query = im.get("search_query","")
    mark_seen = bool(im.get("mark_seen", False))

    offers: List[Offer] = []
    with IMAPClient(host, port=port, ssl=True) as server:
        server.login(user, pwd)
        server.select_folder(folder)
        criteria = ["UNSEEN"] if not mark_seen else ["ALL"]
        if search_query:
            # IMAPClient simple search: use TEXT/FROM etc; keep generic
            criteria = ["TEXT", search_query]
        ids = server.search(criteria)
        if not ids:
            return offers
        fetch = server.fetch(ids, ["RFC822"])
        for mid, data in fetch.items():
            msg = email.message_from_bytes(data[b"RFC822"])
            subject = _decode(msg.get("Subject",""))
            frm = _decode(msg.get("From",""))
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            # Best-effort extraction
            title = subject.strip() or "Subito alert"
            price = parse_price_eur(body)
            url = _extract_first_url(body)
            offers.append(Offer(source="subito_imap", title=title, url=url, price_eur=price, condition="used", extra={"from": frm, "description": body}))
        if mark_seen:
            server.add_flags(ids, ["\\Seen"])
    return offers

def _extract_first_url(text: str) -> str:
    import re
    m = re.search(r"https?://\S+", text or "")
    return m.group(0).strip(").,") if m else ""

def _getenv(name: str) -> str:
    import os
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v
