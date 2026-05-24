# creature_helpers.py
"""生物まわりの共通計算（距離・空腹・移動・捕食など）。"""
import math
import random


def distance_between(a, b) -> float:
    return math.hypot(b.pos[0] - a.pos[0], b.pos[1] - a.pos[1])


def distance_to_point(entity, x: float, y: float) -> float:
    return math.hypot(x - entity.pos[0], y - entity.pos[1])


def current_size(creature) -> float:
    """現在の表示・判定サイズ（traits.base_size）。"""
    return float(creature.traits.get("base_size", 9.0))


# ステージ名 → 次段階へ進む下限年齢キー（life_cycle のキーと対応）
# 新ステージ追加時はこのリストに1行足すだけで get_life_stage が追従する
LIFE_STAGE_PIPELINE = [
    ("Juvenile", "mature"),
    ("Adult", "elder"),
    ("Elder", "death"),
]


def get_life_stage(age: int, life_cycle: dict) -> str:
    """
    life_cycle 方式のライフステージ判定（LIFE_STAGE_PIPELINE 参照）。

    例: mature=280 → age<280 は Juvenile, elder=1800 → Adult, death=3500 → Elder
    age >= death は Creature._check_natural_lifespan で死亡（表示用 Expired）

    # 使用例
    stage = get_life_stage(creature.age, creature.life_cycle)
    """
    if not life_cycle:
        return "Adult"

    for stage_name, next_key in LIFE_STAGE_PIPELINE:
        limit = life_cycle.get(next_key)
        if limit is None:
            continue
        if age < int(limit):
            return stage_name
    return "Expired"


def format_life_stage_line(creature) -> str | None:
    """
    選択個体 UI 用の1行テキスト（life_cycle がある種のみ表示）。
    例: Adult (Age: 1243 / 3500) / Juvenile → Mature in 87 ticks
    """
    life_cycle = creature.life_cycle
    if not life_cycle:
        return None

    stage = get_life_stage(creature.age, life_cycle)
    death = int(life_cycle.get("death", 0))

    if stage == "Juvenile":
        mature_at = int(life_cycle.get("mature", 0))
        ticks = max(0, mature_at - creature.age)
        return f"ライフステージ: {stage} → Mature in {ticks} ticks"

    if death > 0:
        return f"ライフステージ: {stage} (Age: {creature.age} / {death})"
    return f"ライフステージ: {stage} (Age: {creature.age})"


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
    return not target.alive and getattr(target, "remaining_biomass", 0) > 0


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


def bite(predator, prey, attack_power: float = 1.0) -> float:
    """生きている獲物に噛みつきHPダメージを与える。与えたダメージ量を返す。"""
    if not prey.alive:
        return 0.0

    damage = float(attack_power) * 12.0
    prey.hp -= damage

    if prey.hp <= 0:
        prey.become_corpse()

    return damage


def consume_carcass(predator, carcass, bite_gain: float = 1.35) -> float:
    """死骸の残存バイオマスを消費して満腹度を回復。得られた Satiety 量を返す。"""
    if carcass.alive or carcass.remaining_biomass <= 0:
        return 0.0

    base_size = float(predator.traits.get("base_size", 9.0))
    bite_gain = float(bite_gain)
    amount = min(
        carcass.remaining_biomass * 0.45,
        base_size * bite_gain * 1.6,
    )
    carcass.remaining_biomass -= amount * 0.9

    gained = amount * bite_gain
    predator.satiety = min(predator.max_satiety, predator.satiety + gained)

    if carcass.remaining_biomass <= 8.0:
        world = carcass.world
        if world:
            world.return_mana_from_decomposition(carcass.remaining_biomass * 0.8)
        carcass.remaining_biomass = 0.0

    return gained


def try_predate(
    predator,
    target,
    attack_power: float = 1.0,
    bite_gain: float = 1.35,
) -> None:
    """接触時の捕食フロー: bite → 死骸化 → consume_carcass"""
    if target.alive:
        bite(predator, target, attack_power=attack_power)
    if not target.alive:
        consume_carcass(predator, target, bite_gain=bite_gain)


def wander_step(creature, angle_range: float, speed_multiplier: float) -> None:
    creature.wander_angle += random.uniform(-angle_range, angle_range)
    move = creature.get_current_speed() * speed_multiplier
    creature.pos[0] += math.cos(math.radians(creature.wander_angle)) * move
    creature.pos[1] += math.sin(math.radians(creature.wander_angle)) * move


def get_mana_gradient_direction(
    creature, sampling_distance: float = 60.0, angle_step: int = 45
) -> float:
    """マナ濃度が最も高い方向（度数法 0~360）を返す。"""
    if not creature.world or not creature.world.biome_noise:
        return creature.wander_angle

    best_angle = creature.wander_angle
    best_mana = -1.0

    for angle in range(0, 360, angle_step):
        rad = math.radians(angle)
        tx = creature.pos[0] + math.cos(rad) * sampling_distance
        ty = creature.pos[1] + math.sin(rad) * sampling_distance

        tx = max(0, min(creature.world.width, tx))
        ty = max(0, min(creature.world.height, ty))

        mana_mult = creature.world.get_mana_regen_multiplier(tx, ty)

        if mana_mult > best_mana:
            best_mana = mana_mult
            best_angle = angle

    return best_angle
