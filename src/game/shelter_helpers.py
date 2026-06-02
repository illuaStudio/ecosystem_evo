"""ゲーム層: コロニー拠点への避難所解決。"""
from __future__ import annotations

from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.shelter.types import ShelterRef

# Game policy: which actions are permitted while sheltered.
# This list is used to restrict the creature's mind action_defs on enter,
# instead of sim filtering based on injected whitelist on World.
DEFAULT_SHELTER_ALLOWED_ACTION_NAMES = frozenset(
    {
        "SeekShelterAction",
        "FeedAtNestAction",
        "FeedAtAffiliationSiteAction",
        "AffiliationReproduceAction",
    }
)


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
    _restore_mind_after_shelter(creature)


def _restrict_mind_for_shelter(creature) -> None:
    """On entering shelter, restrict the mind's action_defs to only shelter-allowed ones.
    Save previous for restore on exit. This keeps the whitelist logic in game layer.
    """
    mind = getattr(creature, "mind", None)
    if mind is None or not hasattr(mind, "action_defs"):
        return
    current = list(getattr(mind, "action_defs", []))
    allowed = DEFAULT_SHELTER_ALLOWED_ACTION_NAMES
    shelter_defs = [d for d in current if d.get("name") in allowed]
    if shelter_defs and shelter_defs != current:
        setattr(creature, "_pre_shelter_action_defs", current)
        mind.set_action_defs(shelter_defs)
        creature.current_action = None


def _restore_mind_after_shelter(creature) -> None:
    """Restore pre-shelter action_defs when exiting shelter."""
    mind = getattr(creature, "mind", None)
    pre = getattr(creature, "_pre_shelter_action_defs", None)
    if pre is not None and mind is not None and hasattr(mind, "set_action_defs"):
        mind.set_action_defs(pre)
        delattr(creature, "_pre_shelter_action_defs")
        creature.current_action = None


def enter_creature_shelter(creature, ref: ShelterRef) -> None:
    """Game wrapper around sim enter that also restricts mind actions for shelter.
    This keeps the "allowed actions while sheltered" policy in the game layer.
    """
    from src.sim.shelter.helpers import enter_creature_shelter as _sim_enter

    _sim_enter(creature, ref)
    _restrict_mind_for_shelter(creature)
