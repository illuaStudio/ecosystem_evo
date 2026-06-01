"""避難所の解決・出入り・脅威を避けた接近。"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.shelter.types import ShelterRef
from src.sim.utils.movement_helpers import (
    contact_range,
    find_nearest_flee_threat_among,
    move_away_from,
    move_toward_point,
)
from src.sim.utils.position_helpers import entity_xy

if TYPE_CHECKING:
    from src.sim.entities.creature import Creature


def _is_colony_defeated(creature) -> bool:
    from src.sim.utils.affiliation_group_helpers import is_creature_affiliation_defeated

    return is_creature_affiliation_defeated(creature)


def get_hide_radius(creature) -> float:
    """巣に「入った」とみなす半径（colony.hide_radius → deposit_radius）。"""
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
    """この巣穴目標へ直進すると脅威に近づく、または脅威が穴付近にいる。"""
    if threat is None:
        return False
    cx, cy = entity_xy(creature)
    tx_th, ty_th = entity_xy(threat)
    pad = 8.0
    block_r = approach_radius + contact_range(creature, threat, pad)

    if math.hypot(tx_th - tx, ty_th - ty) <= block_r:
        return True

    nest_d = math.hypot(tx - cx, ty - cy)
    threat_d = math.hypot(tx_th - cx, ty_th - cy)
    if nest_d < 1e-3:
        return threat_d <= block_r

    ux = (tx - cx) / nest_d
    uy = (ty - cy) / nest_d
    dot = ux * (tx_th - cx) + uy * (ty_th - cy)
    return dot > 0 and threat_d < nest_d


def resolve_nest_shelter(creature, threat=None) -> ShelterRef | None:
    """所属コロニーの colony_access から最寄り避難所を解決。"""
    affiliation = getattr(creature, "affiliation", None)
    world = getattr(creature, "world", None)
    if world is None or affiliation is None:
        return None
    if _is_colony_defeated(creature):
        return None
    from src.sim.utils.world_object_helpers import resolve_shelter_from_colony

    return resolve_shelter_from_colony(world, affiliation.affiliation_id, creature, threat)


def resolve_creature_shelter(creature, threat=None) -> ShelterRef | None:
    """親オブジェクト優先。未設定時は勢力の colony_access。"""
    from src.sim.utils.world_object_helpers import (
        resolve_shelter_from_colony,
        resolve_shelter_from_parents,
    )

    ref = resolve_shelter_from_parents(creature, threat)
    if ref is not None:
        return ref

    colony = getattr(creature, "affiliation", None)
    world = getattr(creature, "world", None)
    if colony is not None and world is not None:
        return resolve_shelter_from_colony(world, colony.affiliation_id, creature, threat)
    return None


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
    """脅威が穴や進路上にあるときは近づかず離れる。"""
    approach_radius = get_hide_radius(creature)
    if _threat_blocks_approach(
        creature, ref.x, ref.y, threat, approach_radius=approach_radius
    ):
        if threat is not None:
            return move_away_from(creature, threat, speed_multiplier)
        return shelter_distance(creature, ref)
    return move_toward_point(creature, ref.x, ref.y, speed_multiplier)


def collect_threat_species_from_mind(creature) -> tuple[str, ...]:
    """FleeAction / SeekShelterAction の threat_species を集約。"""
    threats: list[str] = []
    for action_def in creature.species.mind_data.get("actions", []):
        if action_def.get("name") not in ("FleeAction", "SeekShelterAction"):
            continue
        raw = action_def.get("params", {}).get("threat_species") or ()
        threats.extend(raw)
    return tuple(dict.fromkeys(threats))


def nearest_shelter_threat(creature, threat_species: tuple[str, ...]):
    return find_nearest_flee_threat_among(
        creature, threat_species, exclude=creature
    )


def sync_shelter_after_defeat(creature) -> None:
    """コロニー敗北時: 隠れ中の個体は死亡。"""
    if not is_creature_sheltered(creature):
        return
    if not _is_colony_defeated(creature):
        return
    creature.hp = 0.0
    clear_creature_shelter(creature)
