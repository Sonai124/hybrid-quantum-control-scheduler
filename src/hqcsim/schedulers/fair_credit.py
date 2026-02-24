from __future__ import annotations
from dataclasses import dataclass
from .base import SchedulerDecision
from .credit_event import CreditState

@dataclass
class FairParams:
    quantum_every_n: int = 5  # serve quantum at least once every N sends if credits exist


class FairCreditScheduler:
    def __init__(self, credit_state: CreditState, params: FairParams):
        self.credit_state = credit_state
        self.params = params
        self._since_q = 0

    def choose(self, now: float, q_len: int, c_len: int) -> SchedulerDecision:
        _ = now

        # If we have credits and quantum is waiting, force quantum every N sends
        if q_len > 0 and not self.credit_state.empty and self._since_q >= self.params.quantum_every_n:
            self._since_q = 0
            return SchedulerDecision(send_quantum=True)

        # If credits full, prefer quantum
        if self.credit_state.full and q_len > 0:
            self._since_q = 0
            return SchedulerDecision(send_quantum=True)

        # Otherwise classical first
        if c_len > 0:
            self._since_q += 1
            return SchedulerDecision(send_classical=True)

        # If no classical, but quantum exists and credits exist, send quantum
        if q_len > 0 and not self.credit_state.empty:
            self._since_q = 0
            return SchedulerDecision(send_quantum=True)

        return SchedulerDecision()