"""戦闘対象（Creature / WorldObject）の共通 API。"""
from src.sim.combat.target_damage import apply_damage_to_target
from src.sim.combat.target_query import (
    colony_access_in_range,
    find_nearest_colony_access,
    find_nearest_hostile_creature,
    find_nearest_prey_creature,
    is_valid_colony_access,
    iter_targets,
    target_closeness,
    target_position,
    vision_range,
)
from src.sim.combat.target_ref import TargetKind, TargetRef

__all__ = [
    "TargetKind",
    "TargetRef",
    "apply_damage_to_target",
    "colony_access_in_range",
    "find_nearest_colony_access",
    "find_nearest_hostile_creature",
    "find_nearest_prey_creature",
    "is_valid_colony_access",
    "iter_targets",
    "target_closeness",
    "target_position",
    "vision_range",
]
