"""ゲーム層: コロニー拠点への避難所解決。"""
from __future__ import annotations

from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.shelter.types import ShelterRef


def resolve_nest_shelter(creature, threat=None) -> ShelterRef | None:
    affiliation = getattr(creature, "affiliation", None)
    world = getattr(creature, "world", None)
    if world is None or affiliation is None:
        return None
    from src.sim.utils.affiliation_group_helpers import is_creature_affiliation_defeated

    if is_creature_affiliation_defeated(creature):
        return None
    from src.sim.utils.world_object_helpers import resolve_shelter_from_affiliation

    return resolve_shelter_from_affiliation(world, affiliation.affiliation_id, creature, threat)


def resolve_creature_shelter(creature, threat=None) -> ShelterRef | None:
    from src.sim.utils.world_object_helpers import (
        resolve_shelter_from_affiliation,
        resolve_shelter_from_parents,
    )

    ref = resolve_shelter_from_parents(creature, threat)
    if ref is not None:
        return ref

    affiliation = getattr(creature, "affiliation", None)
    world = getattr(creature, "world", None)
    if affiliation is not None and world is not None:
        return resolve_shelter_from_affiliation(world, affiliation.affiliation_id, creature, threat)
    return None


def sync_shelter_after_defeat(creature) -> None:
    if not is_creature_sheltered(creature):
        return
    from src.sim.utils.affiliation_group_helpers import is_creature_affiliation_defeated

    if not is_creature_affiliation_defeated(creature):
        return
    creature.hp = 0.0
    clear_creature_shelter(creature)
