from __future__ import annotations

from dataclasses import dataclass

from .base import SchedulerDecision


@dataclass
class CreditState:
    capacity: int
    credits: int = 0

    def add(self, n: int = 1) -> None:
        self.credits = min(self.capacity, self.credits + max(0, n))

    def consume(self, n: int = 1) -> bool:
        n = max(0, n)
        if self.credits >= n:
            self.credits -= n
            return True
        return False

    @property
    def full(self) -> bool:
        return self.credits >= self.capacity

    @property
    def empty(self) -> bool:
        return self.credits <= 0


class CreditEventScheduler:
    """Event/credit-driven scheduler.

    Policy:
    - If credits are FULL and quantum queue has traffic -> send quantum
    - else send classical if available
    - else send quantum if any credits
    """

    def __init__(self, credit_state: CreditState):
        self.credit_state = credit_state

    def choose(self, now: float, q_len: int, c_len: int) -> SchedulerDecision:
        _ = now
        if self.credit_state.full and q_len > 0:
            return SchedulerDecision(send_quantum=True)

        if c_len > 0:
            return SchedulerDecision(send_classical=True)

        if q_len > 0 and not self.credit_state.empty:
            return SchedulerDecision(send_quantum=True)

        return SchedulerDecision()
