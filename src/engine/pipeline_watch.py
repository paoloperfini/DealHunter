from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..models import Offer
from ..scoring import decide_new_price_with_history, trust_score_used, Decision
from ..sources.trovaprezzi import fetch_trovaprezzi_list
from ..sources.idealo import fetch_idealo_list
from ..sources.subito_ingest import ingest_folder
from ..sources.subito_imap import fetch_subito_alerts_imap
from ..notifiers.notifiers import notify_console, notify_filelog, notify_telegram
from ..storage import connect, insert_offer, best_new_reference, Stats


def match_target(offer: Offer, targets: list[dict]) -> Optional[dict]:
    text = (offer.title or "").lower()
    for t in targets:
        if any(k.lower() in text for k in t["keywords"]):
            return t
    return None


def _is_used_offer(off: Offer) -> bool:
    # Fonte Subito = usato (nel tuo workflow)
    if off.source in ("subito_ingest", "subito_imap"):
        return True
    # Se la sorgente scrive condition, prova a interpretarla
    cond = (off.condition or "").lower()
    if "used" in cond or "usato" in cond or "seconda mano" in cond:
        return True
    return False


def _compute_stats_new_only(
    conn,
    *,
    target_name: str,
    window_days: int = 30,
    drop_hours: int = 48,
) -> Stats:
    """
    Stats SOLO per NEW: esclude Subito (ingest/imap).
    Così Min/Media 30g non vengono contaminati dall'usato.
    """
    now = datetime.utcnow()
    t0 = now - timedelta(days=window_days)
    t1 = now - timedelta(hours=drop_hours)

    # 30 days stats (NEW only)
    cur = conn.execute(
        """
        SELECT COUNT(*), MIN(total_eur), AVG(total_eur)
        FROM offers
        WHERE target_name = ?
          AND ts_utc >= ?
          AND total_eur IS NOT NULL
          AND source NOT IN ('subito_ingest', 'subito_imap')
        """,
        (target_name, t0.isoformat()),
    )
    count, min_30d, avg_30d = cur.fetchone()

    # drop window min (NEW only)
    cur = conn.execute(
        """
        SELECT MIN(total_eur)
        FROM offers
        WHERE target_name = ?
          AND ts_utc >= ?
          AND total_eur IS NOT NULL
          AND source NOT IN ('subito_ingest', 'subito_imap')
        """,
        (target_name, t1.isoformat()),
    )
    (min_drop_window,) = cur.fetchone()

    return Stats(
        count=int(count or 0),
        min_30d=float(min_30d) if min_30d is not None else None,
        avg_30d=float(avg_30d) if avg_30d is not None else None,
        min_drop_window=float(min_drop_window) if min_drop_window is not None else None,
    )


def run_once(cfg: Dict[str, Any], imap_cfg: Optional[Dict[str, Any]] = None) -> None:
    """Legacy PC-price watch pipeline (hardware new + Subito ingest for used)."""
    ua = cfg["settings"]["user_agent"]
    delay = float(cfg["settings"].get("polite_delay_seconds", 1.0))
    db_path = cfg["settings"].get("history_db", "data/history.sqlite")

    offers: List[Offer] = []

    # --- NEW SOURCES ---
    if cfg["sources"]["trovaprezzi"]["enabled"]:
        for url in cfg["sources"]["trovaprezzi"]["urls"]:
            try:
                offers.extend(fetch_trovaprezzi_list(url, ua, delay))
            except Exception as e:
                offers.append(
                    Offer(
                        source="trovaprezzi_error",
                        title=f"Errore fetch {url}",
                        url=url,
                        extra={"error": str(e)},
                    )
                )

    if cfg["sources"]["idealo"]["enabled"]:
        for url in cfg["sources"]["idealo"]["urls"]:
            try:
                offers.extend(fetch_idealo_list(url, ua, delay))
            except Exception as e:
                offers.append(
                    Offer(
                        source="idealo_error",
                        title=f"Errore fetch {url}",
                        url=url,
                        extra={"error": str(e)},
                    )
                )

    # --- SUBITO INGEST (NO scraping) ---
    if cfg.get("subito_ingest", {}).get("enabled", False):
        folder = cfg["subito_ingest"]["import_folder"]
        offers.extend(ingest_folder(folder))
        if cfg["subito_ingest"].get("imap_enabled") and imap_cfg:
            offers.extend(fetch_subito_alerts_imap(imap_cfg))

    # Flatten target list
    all_targets: list[dict] = []
    for _cat, items in cfg["targets"].items():
        all_targets.extend(items)

    # --- DB ---
    conn = connect(db_path)
    now = datetime.utcnow()

    matched: list[tuple[Offer, dict]] = []

    def _is_plausible_new_price(total: float, target_great: float) -> bool:
        # Guardrail: se NEW < 50% della soglia "AFFARE", quasi certamente parse glitch
        return total >= (target_great * 0.50)

    # Store into history (but keep parse glitches out of DB)
    for off in offers:
        t = match_target(off, all_targets)
        if not t:
            continue

        store_ok = True

        if off.total_eur is not None and off.source in ("trovaprezzi", "idealo"):
            if not _is_plausible_new_price(float(off.total_eur), float(t["great_price_eur"])):
                store_ok = False
                off.extra["parse_warning"] = "Prezzo NEW troppo basso (parse glitch). Skippato (no storico, no alert)."

        if store_ok:
            matched.append((off, t))
            insert_offer(
                conn,
                ts_utc=now,
                target_name=t["name"],
                source=off.source,
                title=off.title,
                url=off.url,
                total_eur=off.total_eur,
                price_eur=off.price_eur,
                shipping_eur=off.shipping_eur,
                condition=off.condition,
                seller=off.seller,
                location=off.location,
            )
        else:
            # Keep it for console INFO, but don't store
            matched.append((off, t))

    conn.commit()

    # --- NOTIFIERS ---
    alerts_log = os.path.join("data", "alerts.log")
    tg_cfg = cfg["notifiers"].get("telegram", {})
    tg_enabled = bool(tg_cfg.get("enabled", False))
    tg_token = os.environ.get(tg_cfg.get("bot_token_env", ""), "")
    tg_chat = os.environ.get(tg_cfg.get("chat_id_env", ""), "")

    window_days = int(cfg["decision"].get("window_days", 30))
    drop_hours = int(cfg["decision"].get("drop_hours", 48))
    rapid_drop_discount = float(cfg["decision"].get("rapid_drop_discount", 0.08))

    for off, t in matched:
        # Show parse glitches as INFO, never alert
        if off.source in ("trovaprezzi", "idealo") and off.extra.get("parse_warning"):
            if cfg["notifiers"].get("console", True):
                notify_console(off, Decision("INFO", off.extra.get("parse_warning")))
            continue

        # Ignore fetch errors
        if off.source.endswith("_error"):
            continue

        is_used = _is_used_offer(off)

        if is_used:
            # Used: trust score + reference NEW (min recent NEW)
            ref_new = best_new_reference(conn, target_name=t["name"], window_days=7) or float(t["good_price_eur"])
            decision = trust_score_used(off, cfg["trust_used"], new_reference_price=ref_new)

            # --- Enrich context for richer notifiers (USED) ---
            off.extra["is_used"] = True
            off.extra["ref_new_eur"] = ref_new
            off.extra["trust_score"] = getattr(decision, "score", None)

        else:
            # NEW: stats computed only from NEW history (exclude Subito)
            stats_new = _compute_stats_new_only(
                conn,
                target_name=t["name"],
                window_days=window_days,
                drop_hours=drop_hours,
            )
            decision = decide_new_price_with_history(
                off,
                target_good=float(t["good_price_eur"]),
                target_great=float(t["great_price_eur"]),
                stats=stats_new,
                rapid_drop_discount=rapid_drop_discount,
            )

            # --- Enrich context for richer notifiers (NEW) ---
            off.extra["is_used"] = False
            off.extra["stats_min_30d"] = stats_new.min_30d
            off.extra["stats_avg_30d"] = stats_new.avg_30d
            off.extra["stats_count"] = stats_new.count
            off.extra["stats_min_48h"] = stats_new.min_drop_window

        if cfg["notifiers"].get("console", True):
            notify_console(off, decision)

        if cfg["notifiers"].get("file_log", True):
            notify_filelog(alerts_log, off, decision)

        if tg_enabled and tg_token and tg_chat and decision.verdict in ("AFFARE", "BUONO"):
            notify_telegram(tg_token, tg_chat, off, decision)

    conn.close()
