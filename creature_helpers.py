# creature_helpers.py
"""生物まわりの共通計算（距離・空腹・移動・捕食など）。"""
import math
import random


def get_max_energy(creature) -> float:
    return creature.traits.get("max_energy", 400)


def distance_between(a, b) -> float:
    return math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])


def distance_to_point(entity, x: float, y: float) -> float:
    return math.hypot(x - entity.pos[0], y - entity.pos[1])


def energy_ratio(creature) -> float:
    """現在エネルギー / 最大（0〜1）"""
    cap = get_max_energy(creature)
    if cap <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.energy / cap))


def hunger_ratio(creature) -> float:
    """空腹度（0=満腹, 1=空腹）"""
    cap = get_max_energy(creature)
    if cap <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - creature.energy / cap))


def closeness_ratio(creature, other) -> float:
    """視界内での近さ（0=遠い, 1=至近）"""
    vision = creature.get_current_vision()
    if vision <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance_between(creature, other) / vision))


def find_nearest_of_species(creature, species_name: str, exclude=None):
    if not creature.world:
        return None
    return creature.world.get_nearest_creature(
        creature.pos,
        species_name=species_name,
        max_dist=creature.get_current_vision(),
        exclude=exclude,
    )


def is_alive_target(target, species_name: str) -> bool:
    if target is None or not target.alive:
        return False
    return target.species.name == species_name


def is_in_vision(creature, target) -> bool:
    return distance_between(creature, target) <= creature.get_current_vision()


def is_trackable_target(creature, target, species_name: str) -> bool:
    return is_alive_target(target, species_name) and is_in_vision(creature, target)


def contact_range(creature, other, padding: float = 8.0) -> float:
    return (
        creature.traits["base_size"]
        + other.traits.get("base_size", 9)
        + padding
    )


def move_toward(creature, target, speed_multiplier: float = 1.0) -> float:
    """ターゲット方向へ移動し、移動後の距離を返す。"""
    dx = target.pos[0] - creature.pos[0]
    dy = target.pos[1] - creature.pos[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return 0.0

    step = creature.get_current_speed() * speed_multiplier
    creature.pos[0] += (dx / dist) * step
    creature.pos[1] += (dy / dist) * step
    return distance_between(creature, target)


def feed_on(creature, prey, steal_cap: float = 45, efficiency: float = 1.1) -> None:
    stolen = min(steal_cap, prey.energy * 0.8)
    prey.energy -= stolen
    cap = get_max_energy(creature)
    creature.energy = min(cap, creature.energy + stolen * efficiency)
    if prey.energy <= 0:
        prey.alive = False


def wander_step(creature, angle_range: float, speed_multiplier: float) -> None:
    creature.wander_angle += random.uniform(-angle_range, angle_range)
    move = creature.get_current_speed() * speed_multiplier
    creature.pos[0] += math.cos(math.radians(creature.wander_angle)) * move
    creature.pos[1] += math.sin(math.radians(creature.wander_angle)) * move
