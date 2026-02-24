from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class PacketType(str, Enum):
    CLASSICAL = "classical"
    QUANTUM_KEY = "quantum_key"


@dataclass(frozen=True)
class Packet:
    pkt_id: int
    pkt_type: PacketType
    created_at: float
    size_bytes: int = 1500
    meta: Optional[dict[str, Any]] = None
