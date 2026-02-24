from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerDecision:
    send_quantum: bool = False
    send_classical: bool = False
