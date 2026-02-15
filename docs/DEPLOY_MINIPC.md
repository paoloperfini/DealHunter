# Deploy su mini-PC sempre acceso (quando sei pronto)

Quando passerai alla “versione finale”, la strada più semplice è:

## Windows (Task Scheduler)
- crea un'attività che avvia:
  - `python -m src.agent`
- trigger: all'avvio del PC
- opzione: riavvia se si interrompe

## Linux (systemd)
- crea un servizio systemd che esegue:
  - `/path/to/venv/bin/python -m src.agent`
- restart=always

Questo pacchetto è già pronto per lavorare in loop (default ogni 3 ore).
