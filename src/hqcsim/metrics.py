from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .models import Packet, PacketType


@dataclass(frozen=True)
class Summary:
    t_end: float
    delivered_total: int
    dropped_total: int
    delivered_classical: int
    delivered_quantum: int
    mean_latency_classical: float
    mean_latency_quantum: float
    p95_latency_classical: float
    p95_latency_quantum: float


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _p95(xs: List[float]) -> float:
    if not xs:
        return 0.0
    xs2 = sorted(xs)
    idx = int(0.95 * (len(xs2) - 1))
    return xs2[idx]


def summarize(
    delivered: Iterable[Packet],
    dropped: Iterable[Packet],
    latencies: Dict[int, float],
    t_end: float,
) -> Summary:
    d = list(delivered)
    dr = list(dropped)

    c_lats: List[float] = []
    q_lats: List[float] = []
    for p in d:
        lat = latencies.get(p.pkt_id, 0.0)
        if p.pkt_type == PacketType.CLASSICAL:
            c_lats.append(lat)
        else:
            q_lats.append(lat)

    return Summary(
        t_end=t_end,
        delivered_total=len(d),
        dropped_total=len(dr),
        delivered_classical=sum(1 for p in d if p.pkt_type == PacketType.CLASSICAL),
        delivered_quantum=sum(1 for p in d if p.pkt_type == PacketType.QUANTUM_KEY),
        mean_latency_classical=_mean(c_lats),
        mean_latency_quantum=_mean(q_lats),
        p95_latency_classical=_p95(c_lats),
        p95_latency_quantum=_p95(q_lats),
    )
