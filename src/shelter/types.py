"""避難所参照（巣穴・将来の hide_spot など）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShelterRef:
    kind: str  # "nest_hole"
    nest_id: int
    hole_index: int
    x: float
    y: float
