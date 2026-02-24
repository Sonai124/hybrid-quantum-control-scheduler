from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional, Protocol

import simpy

from .models import Packet, PacketType
from .schedulers.base import SchedulerDecision


class Scheduler(Protocol):
    def choose(self, now: float, q_len: int, c_len: int) -> SchedulerDecision: ...


@dataclass
class LinkConfig:
    service_time_s: float = 0.001
    loss_prob: float = 0.0


@dataclass
class SimResult:
    delivered: List[Packet]
    dropped: List[Packet]
    latencies: Dict[int, float]  # pkt_id -> latency


def run_sim(
    classical: List[Packet],
    quantum: List[Packet],
    scheduler: Scheduler,
    link: LinkConfig,
    t_end: float,
    on_tick: Optional[Callable[[float], None]] = None,
    seed: int = 0,
    quantum_credit_consume: Optional[Callable[[int], bool]] = None,
) -> SimResult:
    """Run a discrete-event simulation.

    - classical/quantum: arrival packets (with created_at timestamps)
    - scheduler: decides which queue to serve
    - link: service time + loss
    - on_tick: called frequently to update credit buffers, etc.
    - quantum_credit_consume: called when sending a quantum packet (consume 1 credit)
    """

    env = simpy.Environment()
    c_q: Deque[Packet] = deque()
    q_q: Deque[Packet] = deque()

    delivered: List[Packet] = []
    dropped: List[Packet] = []
    latencies: Dict[int, float] = {}

    rng = random.Random(seed)

    classical_sorted = sorted(classical, key=lambda p: p.created_at)
    quantum_sorted = sorted(quantum, key=lambda p: p.created_at)

    def arrival_process(pkts: List[Packet], queue: Deque[Packet]):
        for p in pkts:
            delay = max(0.0, p.created_at - env.now)
            yield env.timeout(delay)
            queue.append(p)

    def tx_process():
        while env.now < t_end:
            if on_tick:
                on_tick(env.now)

            decision = scheduler.choose(env.now, q_len=len(q_q), c_len=len(c_q))

            pkt: Optional[Packet] = None
            if decision.send_quantum and q_q:
                # Optionally require credits
                if quantum_credit_consume and not quantum_credit_consume(1):
                    # can't send quantum; try classical this tick
                    decision = SchedulerDecision(send_classical=True)
                else:
                    pkt = q_q.popleft()

            if pkt is None and decision.send_classical and c_q:
                pkt = c_q.popleft()

            if pkt is None:
                # idle
                yield env.timeout(0.0001)
                continue

            yield env.timeout(link.service_time_s)

            if rng.random() < link.loss_prob:
                dropped.append(pkt)
            else:
                delivered.append(pkt)
                latencies[pkt.pkt_id] = env.now - pkt.created_at

    env.process(arrival_process(classical_sorted, c_q))
    env.process(arrival_process(quantum_sorted, q_q))
    env.process(tx_process())
    env.run(until=t_end)

    return SimResult(delivered=delivered, dropped=dropped, latencies=latencies)
