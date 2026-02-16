from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .tasks import Task, HardwareWatchTask, TelegramCommandTask
from .pipeline_watch import run_once as hardware_watch_run_once
from .pipeline_commands import run_once as commands_run_once


logger = logging.getLogger(__name__)


@dataclass
class Orchestrator:
    """
    Orchestrator = 'mente' che coordina più task.
    """

    cfg: Dict[str, Any]
    imap_cfg: Optional[Dict[str, Any]] = None

    def run_task_once(self, task: Task) -> None:
        task.run_once(self)

    def run_once(self) -> None:
        # Esecuzione singolo ciclo legacy
        self.run_task_once(HardwareWatchTask())
        self.run_task_once(TelegramCommandTask())

    def run_forever(self, loop_minutes: int) -> None:
        watch_period_s = loop_minutes * 60
        cmd_period_s = int(self.cfg.get("notifiers", {}).get("telegram", {}).get("poll_seconds", 3))

        next_watch = 0.0
        next_cmd = 0.0

        while True:
            now = time.time()

            if now >= next_watch:
                self.run_task_once(HardwareWatchTask())
                next_watch = now + watch_period_s

            if now >= next_cmd:
                self.run_task_once(TelegramCommandTask())
                next_cmd = now + cmd_period_s

            time.sleep(0.2)

    # ---- Pipelines exposed to tasks ----

    def run_hardware_watch_once(self) -> None:
        hardware_watch_run_once(self.cfg, self.imap_cfg)

    def run_telegram_commands_once(self) -> None:
        logger.debug("Telegram command loop tick")
        commands_run_once(self.cfg)
