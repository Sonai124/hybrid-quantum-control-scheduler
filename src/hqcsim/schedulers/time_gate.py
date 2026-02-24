from __future__ import annotations

from dataclasses import dataclass

from .base import SchedulerDecision
from ..models import PacketType


@dataclass(frozen=True)
class GateCycle:
    """Simple periodic gate schedule.

    cycle_s: total cycle time
    quantum_open_s: duration during which quantum queue is preferred
    classical_open_s: duration during which classical queue is preferred
    The rest of the cycle acts as a guard band/idle window.
    """

    cycle_s: float
    quantum_open_s: float
    classical_open_s: float

    def gate_state(self, t: float) -> PacketType:
        x = t % self.cycle_s
        if x < self.quantum_open_s:
            return PacketType.QUANTUM_KEY
        if x < self.quantum_open_s + self.classical_open_s:
            return PacketType.CLASSICAL
        # guard band: treat as classical-allowed (or IDLE); we keep it simple
        return PacketType.CLASSICAL


class TimeGateScheduler:
    def __init__(self, gate: GateCycle):
        self.gate = gate

    def choose(self, now: float, q_len: int, c_len: int) -> SchedulerDecision:
        allowed = self.gate.gate_state(now)
        if allowed == PacketType.QUANTUM_KEY and q_len > 0:
            return SchedulerDecision(send_quantum=True)
        if allowed == PacketType.CLASSICAL and c_len > 0:
            return SchedulerDecision(send_classical=True)

        # fallback: drain the other queue if allowed queue empty
        if q_len > 0:
            return SchedulerDecision(send_quantum=True)
        if c_len > 0:
            return SchedulerDecision(send_classical=True)
        return SchedulerDecision()
