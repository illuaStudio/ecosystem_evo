"""戦闘対象（Creature / 巣穴 spawn_node）の共通 API。"""
from src.sim.combat.target_damage import apply_damage_to_target
from src.sim.combat.target_query import (
    find_nearest_hostile_creature,
    find_nearest_prey_creature,
    find_nearest_spawn_node,
    is_trackable_hostile_creature,
    is_trackable_prey_creature,
    is_valid_spawn_node,
    spawn_node_in_range,
    target_closeness,
    target_position,
)
from src.sim.combat.target_ref import TargetKind, TargetRef

__all__ = [
    "TargetKind",
    "TargetRef",
    "apply_damage_to_target",
    "find_nearest_hostile_creature",
    "find_nearest_prey_creature",
    "find_nearest_spawn_node",
    "is_trackable_hostile_creature",
    "is_trackable_prey_creature",
    "is_valid_spawn_node",
    "spawn_node_in_range",
    "target_closeness",
    "target_position",
]
