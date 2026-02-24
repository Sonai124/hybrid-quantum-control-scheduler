from __future__ import annotations

import random
from typing import Iterator, List

from .models import Packet, PacketType


def poisson_arrivals(lam: float, t_end: float, seed: int = 1) -> Iterator[float]:
    """Yield arrival times for a Poisson process with rate `lam` until `t_end`."""
    if lam <= 0:
        return
        yield  # pragma: no cover
    rng = random.Random(seed)
    t = 0.0
    while True:
        t += rng.expovariate(lam)
        if t >= t_end:
            break
        yield t


def generate_packets(
    pkt_type: PacketType,
    lam: float,
    t_end: float,
    seed: int,
    start_id: int,
) -> List[Packet]:
    pkts: List[Packet] = []
    for i, t in enumerate(poisson_arrivals(lam, t_end, seed=seed), start=0):
        pkts.append(Packet(pkt_id=start_id + i, pkt_type=pkt_type, created_at=t))
    return pkts
