from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from .models import Offer
from .storage import Stats

@dataclass
class Decision:
    verdict: str  # AFFARE / BUONO / ASPETTA / INFO
    reason: str
    score: float = 0.0

def decide_new_price_with_history(
    offer: Offer,
    *,
    target_good: float,
    target_great: float,
    stats: Optional[Stats],
    rapid_drop_discount: float = 0.08
) -> Decision:
    """Decisione per NEW che combina soglie statiche + storico (30gg).
    - Se sotto soglia great => AFFARE
    - Se sotto soglia good => BUONO
    - Se c'è 'rapid drop' (min ultime 48h molto sotto la media 30gg) => BUONO (anche se non sotto soglia)
    - Altrimenti ASPETTA
    """
    if offer.total_eur is None:
        return Decision("INFO", "Prezzo non rilevato.")

    total = offer.total_eur

    # Static thresholds first (semplici e affidabili)
    if total <= target_great:
        return Decision("AFFARE", f"Totale {total:.2f}€ <= soglia AFFARE ({target_great}€).")
    if total <= target_good:
        return Decision("BUONO", f"Totale {total:.2f}€ <= soglia BUONO ({target_good}€).")

    # History-based signals
    if stats and stats.avg_30d and stats.min_drop_window:
        # rapid drop: min recent is at least X% below avg_30d
        if stats.min_drop_window <= stats.avg_30d * (1 - rapid_drop_discount) and total <= stats.min_drop_window * 1.02:
            return Decision(
                "BUONO",
                f"Drop rapido: min(48h)={stats.min_drop_window:.2f}€ <= media(30g)={stats.avg_30d:.2f}€ "
                f"(−{rapid_drop_discount*100:.0f}%+). Totale {total:.2f}€ vicino al minimo recente."
            )

    # Otherwise wait
    if stats and stats.min_30d:
        return Decision("ASPETTA", f"Totale {total:.2f}€ sopra soglie. Min(30g)={stats.min_30d:.2f}€; Media(30g)={stats.avg_30d:.2f}€; campioni={stats.count}.")
    return Decision("ASPETTA", f"Totale {total:.2f}€ sopra soglie (buono {target_good}€ / affare {target_great}€).")

def trust_score_used(offer: Offer, cfg: Dict[str, Any], new_reference_price: Optional[float]) -> Decision:
    # Trust score euristico. L'idea: protezione pagamento + credibilità + non-outlier.
    score = 0.0
    text = (offer.title + " " + (offer.extra.get("description","") or "")).lower()

    # Payment protection
    good = cfg.get("keywords_payment_good", [])
    bad = cfg.get("keywords_payment_bad", [])
    if any(k.lower() in text for k in good):
        score += 25
    if any(k.lower() in text for k in bad):
        score -= 35

    # Condition
    cond = (offer.condition or "").lower()
    if "nuovo" in cond or "mai usato" in cond:
        score += 10
    if "come nuovo" in cond or "eccellente" in cond or "perfetto" in cond:
        score += 12

    # Photos / details proxies
    if offer.extra.get("has_photos"):
        score += 10
    if offer.extra.get("has_details"):
        score += 15

    # Seller reputation (if provided)
    rep = offer.extra.get("seller_reputation")
    if isinstance(rep, (int, float)):
        score += min(30, max(0, rep))  # expected 0..30

    # Price sanity
    if offer.total_eur is not None and new_reference_price is not None:
        if offer.total_eur < new_reference_price * (1 - cfg.get("outlier_discount_vs_new", 0.45)):
            # troppo basso vs nuovo -> sospetto
            score -= 40
        else:
            score += 15

    verdict = "INFO"
    reason_parts = [f"Trust score={score:.0f}"]
    min_score = cfg.get("min_score_to_alert", 70)
    if score >= min_score:
        verdict = "BUONO"
        if offer.total_eur is not None and new_reference_price is not None and offer.total_eur <= new_reference_price * 0.75:
            verdict = "AFFARE"
        reason_parts.append(f">= soglia {min_score}.")
        if new_reference_price is not None:
            reason_parts.append(f"Ref nuovo ~{new_reference_price:.2f}€.")
    else:
        verdict = "ASPETTA"
        reason_parts.append(f"< soglia {min_score} (non abbastanza dati/affidabilità).")

    return Decision(verdict, " ".join(reason_parts), score=score)
