from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SensorPacketPayload:
    ts: float
    x: float
    y: float
    h: float
    idx: int

    # implement to make instances subscriptable:
    def __getitem__(self, item):
        return getattr(self, item)

    def __str__(self):
        return f"SensorPacketPayload[idx: {self.idx} | ts: {self.ts} | x:{self.x}, y:{self.y}, h:{self.h}]"

