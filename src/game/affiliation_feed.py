"""ゲーム層: 拠点備蓄からの給餌判定（種 JSON の affiliation_feed）。"""
from __future__ import annotations

def _satiety_ratio(creature) -> float:
    if creature.max_satiety <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.satiety / creature.max_satiety))


def _satiety_full_above(creature) -> float:
    return float(creature.traits.get("satiety_full_above", 0.85))


def _satiety_feed_target(creature) -> float:
    return _satiety_full_above(creature) * creature.max_satiety


def _satiety_room_until_feed_target(creature) -> float:
    return max(0.0, _satiety_feed_target(creature) - creature.satiety)


def get_affiliation_feed_config(creature) -> dict[str, float]:
    """種 JSON の affiliation_feed（旧 nest_feed も受理）。"""
    species = creature.species
    block = getattr(species, "affiliation_feed", None) or getattr(species, "nest_feed", None)
    if block is None:
        raise KeyError(f"species {species.name}: affiliation_feed block required")
    return block


def affiliation_feed_completion_slack(creature) -> float:
    metabolism = float(creature.traits.get("metabolism_per_tick", 0.5))
    target = _satiety_feed_target(creature)
    return max(metabolism * 2.5, target * 0.003)


def affiliation_feed_completion_ratio_slack(creature) -> float:
    metabolism = float(creature.traits.get("metabolism_per_tick", 0.5))
    max_sat = max(float(creature.max_satiety), 1.0)
    return max(metabolism * 3.0 / max_sat, 0.009)


def is_affiliation_feed_satisfied(creature) -> bool:
    sat = _satiety_ratio(creature)
    full = _satiety_full_above(creature)
    if sat >= full:
        return True
    if round(sat * 100) >= round(full * 100):
        return True

    target = _satiety_feed_target(creature)
    if creature.satiety >= target:
        return True
    if creature.satiety >= target - affiliation_feed_completion_slack(creature):
        return True
    return sat >= full - affiliation_feed_completion_ratio_slack(creature)


def needs_affiliation_feed(creature) -> bool:
    return not is_affiliation_feed_satisfied(creature)


def sync_nutrition_recovery_for_affiliation_feed(creature) -> None:
    """拠点給餌で十分なら sim の nutrition_recovery を解除する。"""
    try:
        get_affiliation_feed_config(creature)
    except KeyError:
        return
    if is_affiliation_feed_satisfied(creature):
        creature.nutrition_recovery = False


def affiliation_stored_mass(creature, default: float = 0.0) -> float:
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


def affiliation_has_storage(creature, min_mass: float = 8.0) -> bool:
    return affiliation_stored_mass(creature) > min_mass


def affiliation_has_usable_storage(creature) -> bool:
    if affiliation_stored_mass(creature) <= 0:
        return False
    return _satiety_room_until_feed_target(creature) > 0


def affiliation_feed_satiety_gain_estimate(creature) -> float:
    cfg = get_affiliation_feed_config(creature)
    feed_per_tick = cfg["feed_per_tick"]
    bite_gain = cfg["bite_gain"]
    if getattr(creature, "affiliation", None) is None:
        return 0.0
    from src.sim.utils.world_object_helpers import get_creature_affiliation_root

    root = get_creature_affiliation_root(creature)
    if root is None or root.storage is None or root.storage.stored_mass <= 0:
        return 0.0

    max_sat = float(creature.max_satiety)
    if float(creature.satiety) >= max_sat:
        return 0.0

    take = min(root.storage.stored_mass, float(feed_per_tick))
    gain = take * float(bite_gain)
    room = max_sat - float(creature.satiety)
    return min(gain, room)


def affiliation_blocks_hunt(creature) -> bool:
    """飢餓時、拠点給餌が可能なら狩りを抑止。"""
    from src.sim.utils.nutrition_helpers import needs_self_feed

    if not needs_self_feed(creature):
        return False
    return affiliation_has_usable_storage(creature)


# 後方互換エイリアス
needs_nest_feed = needs_affiliation_feed
is_nest_feed_satisfied = is_affiliation_feed_satisfied
get_nest_feed_config = get_affiliation_feed_config
nest_has_storage = affiliation_has_storage
nest_has_usable_storage = affiliation_has_usable_storage
nest_stored_mass = affiliation_stored_mass
nest_feed_satiety_gain_estimate = affiliation_feed_satiety_gain_estimate
