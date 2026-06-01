"""compound storage からの給餌可否（物理+種 JSON。ゲームルールではない）。"""
from __future__ import annotations


def _species_feed_block(creature) -> dict | None:
    species = creature.species
    return getattr(species, "affiliation_feed", None) or getattr(species, "nest_feed", None)


def affiliation_storage_mass_for_creature(creature, default: float = 0.0) -> float:
    from src.sim.utils.world_object_helpers import (
        get_creature_affiliation_root,
        get_creature_compound_parent_ids,
        parent_stored_mass,
    )

    if get_creature_compound_parent_ids(creature):
        return parent_stored_mass(creature, default=default)
    root = get_creature_affiliation_root(creature)
    if root is None or root.storage is None:
        return default
    return float(root.storage.stored_mass)


def satiety_room_until_site_feed_target(creature) -> float:
    from src.sim.utils.nutrition_helpers import get_satiety_full_above

    target = get_satiety_full_above(creature) * creature.max_satiety
    return max(0.0, target - creature.satiety)


def creature_can_use_affiliation_storage_feed(creature) -> bool:
    """所属拠点に食料があり、かつ満腹目標まで余地がある。"""
    if _species_feed_block(creature) is None:
        return False
    if affiliation_storage_mass_for_creature(creature) <= 0:
        return False
    return satiety_room_until_site_feed_target(creature) > 0


def hunger_should_skip_hunt_for_storage(creature) -> bool:
    """飢餓時、拠点 storage で給餌できるなら狩りを抑止。"""
    from src.sim.utils.nutrition_helpers import needs_self_feed

    if not needs_self_feed(creature):
        return False
    return creature_can_use_affiliation_storage_feed(creature)
