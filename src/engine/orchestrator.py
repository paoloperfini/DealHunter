from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable

from .tasks import Task, HardwareWatchTask, TelegramCommandTask
from .pipeline_watch import run_once as hardware_watch_run_once
from .pipeline_commands import run_once as commands_run_once


@dataclass
class Orchestrator:
    """
    Orchestrator = 'mente' che coordina più task.

    Opzione B: è un modulo separato (engine/) con API stabile:
    - puoi aggiungere nuovi Task (es. premium_vehicle) senza toccare agent.py
    - puoi in futuro parallelizzare task/worker senza cambiare interfaccia
    """

    cfg: Dict[str, Any]
    imap_cfg: Optional[Dict[str, Any]] = None

    def run_task_once(self, task: Task) -> None:
        task.run_once(self)

    def run_once(self) -> None:
        # Per ora: un solo task legacy (hardware + Subito ingest).
        # Domani: caricheremo tasks dinamici (Telegram) e li scheduliamo.
        self.run_task_once(HardwareWatchTask())
        # Also run Telegram commands (non-blocking, handles updates)
        self.run_task_once(TelegramCommandTask())

    def run_forever(self, loop_minutes: int) -> None:
        while True:
            self.run_once()
            time.sleep(loop_minutes * 60)

    # ---- Pipelines exposed to tasks (workers entrypoints) ----

    def run_hardware_watch_once(self) -> None:
        hardware_watch_run_once(self.cfg, self.imap_cfg)

    def run_telegram_commands_once(self) -> None:
        commands_run_once(self.cfg)
