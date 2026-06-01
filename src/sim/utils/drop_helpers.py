"""死後・イベントからの WorldObject ドロップ（spawn_drop）。"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from src.sim.entities.world_object import WorldObject
from src.sim.utils.position_helpers import entity_xy


def apply_spawn_drop_step(creature, params: Mapping[str, Any] | None = None) -> Optional[WorldObject]:
    world = getattr(creature, "world", None)
    if world is None:
        return None
    wos = getattr(world, "world_object_system", None)
    if wos is None:
        return None

    spec = dict(params or {})
    type_ref = str(spec.get("type", "field_bulk"))
    fill = spec.get("fill")
    if fill is None:
        fill = {"mode": "creature_metric"}

    cx, cy = entity_xy(creature)
    overrides: Dict[str, Any] = dict(spec.get("overrides") or {})
    if "pickup_species_filter" not in overrides:
        overrides["pickup_species_filter"] = creature.species.name

    rate = float(creature.traits.get("corpse_decay_rate", 0.00003))
    color = tuple(getattr(creature.species, "color", (140, 120, 90)))
    caps = dict(overrides.get("capabilities") or {})
    pickup = dict(caps.get("pickup") or {})
    decay = dict(pickup.get("decay") or {})
    decay["rate"] = rate
    pickup["decay"] = decay
    caps["pickup"] = pickup
    render = dict(caps.get("render") or {})
    render.setdefault("color", list(color))
    caps["render"] = render
    overrides["capabilities"] = caps

    return wos.spawn_instance(
        type_ref=type_ref,
        x=cx,
        y=cy,
        fill=fill,
        overrides=overrides,
        origin="spawn",
        creature=creature,
    )
