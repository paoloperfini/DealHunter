# PC Price Hunter Agent (Italia/EU) — monitor “comprare vs aspettare”
> **Questo pacchetto NON acquista nulla.** Monitora prezzi e annunci, valuta rischio, e invia alert.

## Perché Subito.it è “fondamentale” ma va trattato diversamente
Subito.it nel suo `robots.txt` dichiara esplicitamente che l'uso di metodi automatici per accedervi è vietato salvo permesso.  
Per rispettare questo vincolo, questo progetto **NON effettua scraping automatico di Subito.it**.

✅ Invece, integra Subito così:
1. **Crea le ricerche salvate** nell’app/sito Subito (es. “RTX 5090”, “9800X3D”, “DDR5 2x64 128GB”, “990 PRO 2TB”).
2. **Attiva gli avvisi** (email o notifiche).
3. **Inoltra** le email di avviso (o copia/incolla annunci) verso l’agente tramite:
   - parsing della casella email (IMAP) **oppure**
   - import da file `.jsonl` / `.csv` (manuale o semi-automatico).

Fonti: robots Subito.it. 

## Fonti prezzi “nuovo”
- **Trovaprezzi** (pagine confronto prezzi)
- **Idealo** (pagine confronto prezzi)

⚠️ Nota: anche per questi siti, il web cambia. Qui usiamo richieste *molto leggere* + cache + backoff.
Se un sito blocca, il modulo va aggiornato.

## Funzioni principali
- Watchlist SKU (GPU/CPU/RAM/SSD/MOBO) + soglie prezzo
- Normalizzazione prodotto (titolo → marca/modello)
- Decisione: **AFFARE / BUONO / ASPETTA**
- Per usato (Subito import/email): **trust score** basato su:
  - protezione pagamento (Subito Assicurazione / PayPal)
  - recensioni/credibilità venditore (se presenti nel contenuto)
  - outlier pricing (troppo basso = rischio)

## Setup rapido
### 1) Requisiti
- Python 3.11+
- Windows / Linux / macOS

### 2) Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Configura
Copia e modifica:
- `config/config.yaml`
- facoltativo: `config/imap.yaml` (se vuoi parsing email)

### 4) Esegui
```bash
python -m src.agent --once
# oppure in loop
python -m src.agent
```

## Subito: integrazione email (consigliata)
Se vuoi farlo in modo “quasi automatico” senza scraping:
- crea una regola Gmail che **inoltra** gli avvisi Subito a una casella dedicata (o etichetta)
- l’agente legge via IMAP (es. Gmail) e estrae titolo/prezzo/località/link
- se l’email non include abbastanza dati, l’agente ti chiede “manual review” e non genera alert aggressivi

## Output (alert)
- Console (sempre)
- File `data/alerts.log`
- Opzionale: Telegram (via bot token)

## Personalizzazione
- aggiungi SKU e parole chiave in `config/config.yaml`
- imposta soglie “affare/buono” e parametri trust per usato

---

## Struttura progetto
- `src/sources/` fetcher per sorgenti
- `src/scoring.py` logica “compra vs aspetta” + trust score
- `src/notifiers/` canali alert
- `data/` cache e log

Buona caccia (scientifica) 🛰️


## Storico prezzi (SQLite) — “momento migliore”
Da v2 l’agente salva ogni rilevazione in `data/history.sqlite` e calcola:
- minimo e media ultimi 30 giorni per ogni target (CPU/GPU/RAM/SSD…)
- “drop rapido” (min ultimi 48h vs media 30gg)
- decisione più intelligente: **AFFARE / BUONO / ASPETTA** basata su storico + soglie

Questo è il pezzo che rende l’agente davvero “studioso” (comprare ora vs aspettare).


## Patch Idealo parser + guardrail prezzi
- Idealo: estrazione prezzo da JSON-LD/meta (più affidabile)
- Guardrail: se un prezzo NEW è < 50% della soglia "AFFARE" configurata, viene considerato parse glitch (niente storico, niente alert)
