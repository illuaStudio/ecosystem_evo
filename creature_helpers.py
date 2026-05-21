# creature_helpers.py
"""生物まわりの共通計算（距離・空腹・移動・捕食など）。"""
import math
import random


def distance_between(a, b) -> float:
    return math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])


def distance_to_point(entity, x: float, y: float) -> float:
    return math.hypot(x - entity.pos[0], y - entity.pos[1])


def satiety_ratio(creature) -> float:
    """満腹度の割合（0〜1）"""
    if creature.max_satiety <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.satiety / creature.max_satiety))


def hunger_ratio(creature) -> float:
    """空腹度（0=満腹, 1=空腹）"""
    return 1.0 - satiety_ratio(creature)


def hp_ratio(creature) -> float:
    """HPの割合（0〜1）"""
    if creature.max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.hp / creature.max_hp))


def closeness_ratio(creature, other) -> float:
    """視界内での近さ（0=遠い, 1=至近）"""
    vision = creature.get_current_vision()
    if vision <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance_between(creature, other) / vision))


def has_edible_carcass(target) -> bool:
    return not target.alive and getattr(target, "carcass_units", 0) > 0


def is_living_prey(target, species_name: str) -> bool:
    return target is not None and target.alive and target.species.name == species_name


def is_edible_target(creature, target, species_name: str) -> bool:
    if target is None or target is creature:
        return False
    if target.species.name != species_name:
        return False
    return target.alive or has_edible_carcass(target)


def is_in_vision(creature, target) -> bool:
    return distance_between(creature, target) <= creature.get_current_vision()


def is_trackable_target(creature, target, species_name: str) -> bool:
    return is_edible_target(creature, target, species_name) and is_in_vision(creature, target)


def find_nearest_edible(creature, species_name: str, exclude=None):
    if not creature.world:
        return None

    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_edible_target(creature, other, species_name):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


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


def bite(predator, prey) -> float:
    """生きている獲物に噛みつきHPダメージを与える。与えたダメージ量を返す。"""
    if not prey.alive:
        return 0.0

    damage = predator.traits.get("attack_power", 1.0) * 12.0
    prey.hp -= damage

    if prey.hp <= 0:
        prey.hp = 0
        prey.alive = False
        prey.carcass_units = prey.max_hp

    return damage


def consume_carcass(predator, carcass) -> float:
    """死骸から満腹度を回復。得られた Satiety 量を返す。"""
    if carcass.alive or carcass.carcass_units <= 0:
        return 0.0

    taken = min(
        carcass.carcass_units,
        predator.traits.get("attack_power", 1.0) * 8.0,
    )
    carcass.carcass_units -= taken

    gain = taken * predator.traits.get("bite_gain", 1.35)
    predator.satiety = min(predator.max_satiety, predator.satiety + gain)
    return gain


def try_predate(predator, target) -> None:
    """接触時の捕食フロー: bite → 死骸化 → consume_carcass"""
    if target.alive:
        bite(predator, target)
    if not target.alive:
        consume_carcass(predator, target)


def wander_step(creature, angle_range: float, speed_multiplier: float) -> None:
    creature.wander_angle += random.uniform(-angle_range, angle_range)
    move = creature.get_current_speed() * speed_multiplier
    creature.pos[0] += math.cos(math.radians(creature.wander_angle)) * move
    creature.pos[1] += math.sin(math.radians(creature.wander_angle)) * move
