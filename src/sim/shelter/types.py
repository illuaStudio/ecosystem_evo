"""避難所参照（affiliation_access WorldObject）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ShelterKind = Literal["compound_access", "affiliation_access"]


@dataclass(frozen=True)
class ShelterRef:
    kind: ShelterKind
    x: float
    y: float
    object_id: str = ""
    parent_id: str = ""
