"""マップ上の環境発生源（毒霧など）を管理する。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

if TYPE_CHECKING:
    from src.sim.systems.world import World


def _normalize_tags(raw: Any) -> Tuple[str, ...]:
    if raw is None:
        return ("poison",)
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(x) for x in raw if x)


@dataclass
class FieldEmitter:
    """一定半径内に環境効果を与えるワールドオブジェクト。"""

    id: int
    emitter_type: str
    x: float
    y: float
    radius: float
    hp_drain_per_dt: float = 0.0
    hp_regen_per_dt: float = 0.0
    tags: Tuple[str, ...] = field(default_factory=lambda: ("poison",))


class FieldEmitterSystem:
    DEFAULT_POISON_FOG = {
        "type": "poison_fog",
        "radius": 100.0,
        "hp_drain_per_dt": 0.06,
        "tags": ["poison"],
    }

    def __init__(self, world: "World") -> None:
        self.world = world
        self.emitters: List[FieldEmitter] = []
        self._next_id = 1
        self._type_defaults: Dict[str, Dict] = {}

    def init_from_config(self, cfg: Dict | None) -> None:
        self.emitters.clear()
        self._next_id = 1
        self._type_defaults.clear()
        if not cfg:
            return

        defaults = dict(cfg.get("defaults") or {})
        for key, value in (cfg.get("types") or {}).items():
            if isinstance(value, dict):
                self._type_defaults[str(key)] = dict(value)

        for entry in cfg.get("sources") or cfg.get("emitters") or []:
            if isinstance(entry, dict):
                self._add_from_entry(entry, defaults)

    def _resolve_entry(self, entry: Dict, global_defaults: Dict) -> Dict:
        emitter_type = str(entry.get("type", global_defaults.get("type", "poison_fog")))
        merged = dict(self.DEFAULT_POISON_FOG)
        merged.update(global_defaults)
        merged.update(self._type_defaults.get(emitter_type, {}))
        merged.update(entry)
        merged["type"] = emitter_type
        return merged

    def _add_from_entry(self, entry: Dict, global_defaults: Dict) -> None:
        if "x" not in entry or "y" not in entry:
            return
        data = self._resolve_entry(entry, global_defaults)
        emitter = FieldEmitter(
            id=self._next_id,
            emitter_type=str(data["type"]),
            x=float(data["x"]),
            y=float(data["y"]),
            radius=max(1.0, float(data.get("radius", 100.0))),
            hp_drain_per_dt=max(0.0, float(data.get("hp_drain_per_dt", 0.0))),
            hp_regen_per_dt=max(0.0, float(data.get("hp_regen_per_dt", 0.0))),
            tags=_normalize_tags(data.get("tags")),
        )
        self._next_id += 1
        self.emitters.append(emitter)

    def sample_modifiers(
        self,
        creature: Any,
        x: float,
        y: float,
        *,
        immunities: Sequence[str] | None = None,
    ):
        from src.sim.utils.field_modifiers import FieldModifiers, get_field_immunities

        if not self.emitters:
            return FieldModifiers()

        immune = set(immunities or get_field_immunities(creature))
        regen = 0.0
        drain = 0.0
        px, py = float(x), float(y)

        for emitter in self.emitters:
            if math.hypot(px - emitter.x, py - emitter.y) > emitter.radius:
                continue
            if immune.intersection(emitter.tags):
                continue
            regen += emitter.hp_regen_per_dt
            drain += emitter.hp_drain_per_dt

        return FieldModifiers(hp_regen_per_dt=regen, hp_drain_per_dt=drain)
