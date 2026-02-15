from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# Forward ref via Protocol to avoid import cycle
class OrchestratorLike(Protocol):
    def run_hardware_watch_once(self) -> None: ...
    def run_telegram_commands_once(self) -> None: ...


class Task(Protocol):
    def run_once(self, orch: OrchestratorLike) -> None: ...


@dataclass(frozen=True)
class HardwareWatchTask:
    """Task legacy: PC hardware nuovo + ingest usato da Subito."""

    def run_once(self, orch: OrchestratorLike) -> None:
        orch.run_hardware_watch_once()


@dataclass(frozen=True)
class TelegramCommandTask:
    """Task: Poll and handle Telegram bot commands."""

    def run_once(self, orch: OrchestratorLike) -> None:
        orch.run_telegram_commands_once()
