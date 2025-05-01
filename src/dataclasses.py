from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SensorPacketPayload:
    ts = float
    x = float
    y = float
    h = float
    idx = int


