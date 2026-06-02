"""避難所の幾何・接近（所属解決は game.shelter_helpers）。"""
from __future__ import annotations

import math

from src.sim.shelter.state import is_creature_sheltered
from src.sim.shelter.types import ShelterRef
from src.sim.utils.movement_helpers import (
    contact_range,
    find_nearest_flee_threat_among,
    move_away_from,
    move_toward_point,
)
from src.sim.utils.position_helpers import entity_xy


def get_hide_radius(creature) -> float:
    aff_data = getattr(creature.species, "affiliation_data", None) or {}
    if "hide_radius" in aff_data:
        return float(aff_data["hide_radius"])
    if "deposit_radius" in aff_data:
        return float(aff_data["deposit_radius"])
    return 30.0


def _threat_blocks_approach(
    creature,
    tx: float,
    ty: float,
    threat,
    *,
    approach_radius: float,
) -> bool:
    if threat is None:
        return False
    cx, cy = entity_xy(creature)
    tx_th, ty_th = entity_xy(threat)
    pad = 8.0
    block_r = approach_radius + contact_range(creature, threat, pad)

    if math.hypot(tx_th - tx, ty_th - ty) <= block_r:
        return True

    target_d = math.hypot(tx - cx, ty - cy)
    threat_d = math.hypot(tx_th - cx, ty_th - cy)
    if target_d < 1e-3:
        return threat_d <= block_r

    ux = (tx - cx) / target_d
    uy = (ty - cy) / target_d
    dot = ux * (tx_th - cx) + uy * (ty_th - cy)
    return dot > 0 and threat_d < target_d


def shelter_distance(creature, ref: ShelterRef) -> float:
    cx, cy = entity_xy(creature)
    return math.hypot(ref.x - cx, ref.y - cy)


def is_at_shelter(creature, ref: ShelterRef, radius: float | None = None) -> bool:
    r = get_hide_radius(creature) if radius is None else float(radius)
    return shelter_distance(creature, ref) <= r


def enter_creature_shelter(creature, ref: ShelterRef) -> None:
    creature.shelter = ref


def move_toward_shelter_avoiding_threat(
    creature,
    ref: ShelterRef,
    threat,
    *,
    speed_multiplier: float = 1.5,
) -> float:
    approach_radius = get_hide_radius(creature)
    if _threat_blocks_approach(
        creature, ref.x, ref.y, threat, approach_radius=approach_radius
    ):
        if threat is not None:
            return move_away_from(creature, threat, speed_multiplier)
        return shelter_distance(creature, ref)
    return move_toward_point(creature, ref.x, ref.y, speed_multiplier)


def collect_threat_species_from_mind(creature) -> tuple[str, ...]:
    """Collect threat_species from any actions in mind_data that declare them.
    Action names are game-defined, but we look for the param generically.
    """
    threats: list[str] = []
    for action_def in creature.species.mind_data.get("actions", []):
        params = action_def.get("params", {}) or {}
        if "threat_species" in params:
            raw = params.get("threat_species") or ()
            threats.extend(raw)
    return tuple(dict.fromkeys(threats))


def nearest_shelter_threat(creature, threat_species: tuple[str, ...]):
    return find_nearest_flee_threat_among(
        creature, threat_species, exclude=creature
    )
