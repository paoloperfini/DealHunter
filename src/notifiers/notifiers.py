from __future__ import annotations
import os
from ..scoring import Decision
from ..models import Offer

def notify_console(offer: Offer, decision: Decision):
    print(f"[{decision.verdict}] {offer.source} | {offer.title}")
    print(f"  URL: {offer.url}")
    if offer.total_eur is not None:
        print(f"  Totale: {offer.total_eur:.2f}€ (prezzo={offer.price_eur}€, sped={offer.shipping_eur})")
    print(f"  Motivo: {decision.reason}")
    print("-"*80)

def notify_filelog(path: str, offer: Offer, decision: Decision):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{offer.ts.isoformat()}\t{decision.verdict}\t{offer.source}\t{offer.total_eur}\t{offer.title}\t{offer.url}\t{decision.reason}\n")

def _fmt_eur(x) -> str:
    try:
        if x is None:
            return "—"
        return f"{float(x):.2f}€"
    except Exception:
        return "—"

def _pct(delta: float) -> str:
    s = f"{delta*100:.1f}%"
    if delta > 0:
        return f"+{s}"
    return s

def _telegram_build_message(offer: Offer, decision: Decision) -> str:
    # Context injected by agent.py (best-effort)
    is_used = bool(offer.extra.get("is_used", False))
    ref_new = offer.extra.get("ref_new_eur")
    trust = offer.extra.get("trust_score")
    min30 = offer.extra.get("stats_min_30d")
    avg30 = offer.extra.get("stats_avg_30d")
    n30 = offer.extra.get("stats_count")
    min48 = offer.extra.get("stats_min_48h")

    # Emojis + header
    if decision.verdict == "AFFARE":
        verdict_emoji = "🔥"
    elif decision.verdict == "BUONO":
        verdict_emoji = "🟢"
    else:
        verdict_emoji = "ℹ️"

    type_emoji = "♻️" if is_used else "🆕"
    src = (offer.source or "").strip()

    total = offer.total_eur
    price = offer.price_eur
    ship = offer.shipping_eur

    lines = []
    lines.append(f"{verdict_emoji} {decision.verdict} {type_emoji}  {offer.title}")
    if total is not None:
        if ship is None:
            lines.append(f"💶 Totale: {_fmt_eur(total)}")
        else:
            lines.append(f"💶 Totale: {_fmt_eur(total)}  (prezzo {_fmt_eur(price)} + sped {_fmt_eur(ship)})")

    # NEW context
    if not is_used:
        if min30 is not None:
            lines.append(f"📉 NEW 30g: min {_fmt_eur(min30)} | media {_fmt_eur(avg30)} | n={n30}")
            if total is not None and avg30:
                try:
                    vs_avg = (float(total) / float(avg30)) - 1.0
                    lines.append(f"📊 vs media(30g): {_pct(vs_avg)}")
                except Exception:
                    pass
        if min48 is not None:
            lines.append(f"⏱️ NEW 48h: min {_fmt_eur(min48)}")
    else:
        # USED context
        if trust is not None:
            lines.append(f"🛡️ Trust: {int(float(trust))}/100")
        if ref_new is not None and total is not None:
            try:
                disc = 1.0 - (float(total) / float(ref_new))
                lines.append(f"🆕 Ref NEW (7g): {_fmt_eur(ref_new)} | sconto {_pct(disc)}")
            except Exception:
                lines.append(f"🆕 Ref NEW (7g): {_fmt_eur(ref_new)}")

    # Decision reason (compact)
    reason = (decision.reason or "").strip()
    if reason:
        if len(reason) > 260:
            reason = reason[:257] + "..."
        lines.append(f"🧠 {reason}")

    lines.append(f"🔗 {offer.url}")
    if src:
        lines.append(f"🏷️ Fonte: {src}")

    return "\n".join(lines)

def notify_telegram(token: str, chat_id: str, offer: Offer, decision: Decision):
    import requests
    msg = _telegram_build_message(offer, decision)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(
        url,
        json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": True},
        timeout=15
    )

def get_telegram_updates(token: str, offset: int = 0, timeout: int = 5) -> tuple[list[dict], int]:
    """
    Fetch updates from Telegram Bot API.
    Returns: (list of updates, highest update_id) or ([], offset) if no updates.
    """
    import requests
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        resp = requests.get(
            url,
            params={"offset": offset, "timeout": timeout},
            timeout=timeout + 5
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return [], offset
        
        updates = data.get("result", [])
        if not updates:
            return [], offset
        
        # Return updates and the next offset (highest update_id + 1)
        max_update_id = max(u.get("update_id", 0) for u in updates)
        return updates, max_update_id + 1
    except Exception as e:
        print(f"⚠️ Error fetching Telegram updates: {e}")
        return [], offset

def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    import requests
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"⚠️ Error sending Telegram message: {e}")
        return False
