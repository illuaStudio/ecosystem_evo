# creature_helpers.py
"""生物まわりの共通計算（距離・空腹・移動・捕食など）。"""
import math
import random

from src.utils.position_helpers import entity_xy


def distance_between(a, b) -> float:
    ax, ay = entity_xy(a)
    bx, by = entity_xy(b)
    return math.hypot(bx - ax, by - ay)


def distance_to_point(entity, x: float, y: float) -> float:
    ex, ey = entity_xy(entity)
    return math.hypot(x - ex, y - ey)


class PointTarget:
    """座標のみの移動ターゲット（巣など）。"""

    __slots__ = ("pos",)

    def __init__(self, x: float, y: float):
        self.pos = [float(x), float(y)]


def move_toward_point(
    creature,
    x: float,
    y: float,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
) -> float:
    """座標へ移動し、移動後の距離を返す。"""
    return move_toward(creature, PointTarget(x, y), speed_multiplier, dt)


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
    age >= death は LifeCycleManager で自然死（表示用 Expired）

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


TRAIT_DISPLAY_LABELS = {
    "base_size": "サイズ(base)",
    "max_size": "サイズ上限",
    "growth_rate": "成長率",
    "base_speed": "基礎速度",
    "base_vision": "視界",
    "max_hp": "最大HP",
    "max_satiety": "最大満腹",
    "metabolism_rate": "代謝",
    "corpse_decompose_rate": "死骸分解",
    "satiety_hungry_below": "飢餓閾値",
    "satiety_full_above": "満腹閾値",
}


def _format_trait_number(value: float) -> str:
    av = abs(value)
    if av >= 100:
        return f"{value:.0f}"
    if av >= 10:
        return f"{value:.1f}"
    if av >= 1:
        return f"{value:.2f}"
    return f"{value:.4f}"


def _format_trait_delta(delta: float) -> str:
    if abs(delta) < 1e-9:
        return "±0"
    sign = "+" if delta > 0 else ""
    return f"{sign}{_format_trait_number(delta)}"


def format_individual_trait_lines(creature) -> list[str]:
    """選択個体 UI 用: trait_variance 対象の実値・種基本値・差分（全種同一順）。"""
    from src.entities.species import INDIVIDUAL_TRAIT_DISPLAY_ORDER

    variance = getattr(creature.species, "trait_variance", None) or {}
    if not variance:
        return []

    base_traits = creature.species.traits
    lines: list[str] = []
    for key in INDIVIDUAL_TRAIT_DISPLAY_ORDER:
        if key not in variance or key not in creature.traits:
            continue
        actual = float(creature.traits[key])
        base = float(base_traits.get(key, actual))
        label = TRAIT_DISPLAY_LABELS.get(key, key)
        delta_str = _format_trait_delta(actual - base)
        lines.append(
            f"  {label}: {_format_trait_number(actual)}"
            f" (基本 {_format_trait_number(base)}, Δ{delta_str})"
        )
    return lines


def satiety_ratio(creature) -> float:
    """満腹度の割合（0〜1）"""
    if creature.max_satiety <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.satiety / creature.max_satiety))


def hunger_ratio(creature) -> float:
    """空腹度（0=満腹, 1=空腹）。ManaWander 等の連続 utility 用。"""
    return 1.0 - satiety_ratio(creature)


class NutritionState:
    HUNGRY = "hungry"
    NORMAL = "normal"
    FULL = "full"


NUTRITION_LABELS = {
    NutritionState.HUNGRY: "飢餓",
    NutritionState.NORMAL: "通常",
    NutritionState.FULL: "満腹",
}


def get_satiety_hungry_below(creature) -> float:
    """満腹度比率がこれ以下なら飢餓。"""
    return float(creature.traits.get("satiety_hungry_below", 0.15))


def get_satiety_full_above(creature) -> float:
    """満腹度比率の目標上限（巣での食事停止・HUD「満腹」表示）。"""
    return float(creature.traits.get("satiety_full_above", 0.85))


def satiety_feed_target(creature) -> float:
    """巣食事の満腹度目標（絶対値）。"""
    return get_satiety_full_above(creature) * creature.max_satiety


def satiety_room_until_feed_target(creature) -> float:
    """巣で satiety_full_above まで回復できる余地。"""
    return max(0.0, satiety_feed_target(creature) - creature.satiety)


def needs_nest_feed(creature) -> bool:
    """巣食事の余地がある（full_above 未満）。"""
    return satiety_room_until_feed_target(creature) > 0


def get_nutrition_state(creature) -> str:
    sat = satiety_ratio(creature)
    if sat <= get_satiety_hungry_below(creature):
        return NutritionState.HUNGRY
    if sat >= get_satiety_full_above(creature):
        return NutritionState.FULL
    return NutritionState.NORMAL


def is_hungry(creature) -> bool:
    """瞬間的な飢餓（HUD 用）。行動 AI は needs_self_feed を使う。"""
    return get_nutrition_state(creature) == NutritionState.HUNGRY


def update_nutrition_recovery(creature) -> None:
    """回復モードのラッチを満腹度に応じて更新する。"""
    if not getattr(creature, "alive", True):
        creature.nutrition_recovery = False
        return
    sat = satiety_ratio(creature)
    if sat <= get_satiety_hungry_below(creature):
        creature.nutrition_recovery = True
    elif sat >= get_satiety_full_above(creature):
        creature.nutrition_recovery = False


def needs_self_feed(creature) -> bool:
    """自己給餌モード（一度飢餓に入ったら satiety_full_above まで維持）。"""
    update_nutrition_recovery(creature)
    return bool(getattr(creature, "nutrition_recovery", False))


def is_satiated(creature) -> bool:
    """satiety_full_above 以上（巣食事不要・HUD 満腹表示）。"""
    return not needs_nest_feed(creature)


def format_nutrition_status(creature) -> str:
    """HUD 用: 栄養状態と満腹度比率。"""
    label = NUTRITION_LABELS[get_nutrition_state(creature)]
    if needs_self_feed(creature) and not is_hungry(creature):
        label = f"{label}・回復中"
    return f"栄養: {label} ({satiety_ratio(creature) * 100:.0f}%)"


def format_carry_status(creature) -> str | None:
    """HUD 用: コロニー運搬チャンクの状態。運搬していなければ None。"""
    colony = getattr(creature, "colony", None)
    if colony is None:
        return None
    if not colony.is_carrying:
        return "運搬: なし"
    max_carry = get_haul_max_carry(creature)
    src = ""
    carcass = colony.carried_carcass
    if carcass is not None:
        src = f"（元: {carcass.species.name}"
        if has_edible_carcass(carcass):
            src += f", 現場残 {carcass.remaining_biomass:.1f}"
        src += "）"
    return (
        f"運搬: {colony.carried_biomass:.1f} / 上限 {max_carry:.1f}{src}"
    )


def get_haul_max_carry(creature, default: float = 50.0) -> float:
    """巣持ち帰り（ReturnToNestAction）の base_max_carry を種定義から取得。"""
    mind_data = getattr(creature.species, "mind_data", {}) or {}
    for action_def in mind_data.get("actions", []):
        if action_def.get("name") != "ReturnToNestAction":
            continue
        params = action_def.get("params", {}) or {}
        if "base_max_carry" in params:
            return max(0.0, float(params["base_max_carry"]))
    return default


def nest_stored_food(creature, default: float = 0.0) -> float:
    world = getattr(creature, "world", None)
    if world is None:
        return default
    colony = getattr(creature, "colony", None)
    if colony is None:
        return default
    nest = world.nest_system.get_creature_nest(creature)
    if nest is None:
        return default
    return float(nest.stored_food)


def nest_has_food(creature, min_food: float = 8.0) -> bool:
    """stored_food が絶対量の下限を超えるか（粗い判定）。"""
    return nest_stored_food(creature) > min_food


def nest_feed_satiety_gain_estimate(
    creature,
    *,
    max_take_ratio: float = 0.14,
    bite_gain: float = 1.15,
) -> float:
    """次の1ティックで巣から得られる満腹度の見積もり。"""
    world = getattr(creature, "world", None)
    if world is None:
        return 0.0
    colony = getattr(creature, "colony", None)
    if colony is None:
        return 0.0
    nest = world.nest_system.get_creature_nest(creature)
    if nest is None or nest.stored_food <= 0:
        return 0.0

    hunger_room = satiety_room_until_feed_target(creature)
    if hunger_room <= 0:
        return 0.0

    members = max(
        1, world.nest_system.member_count(nest.id, creature.species.name)
    )
    per_member_ratio = float(max_take_ratio) / members
    max_take = nest.stored_food * per_member_ratio
    take = min(nest.stored_food, max_take, hunger_room / float(bite_gain))
    return take * float(bite_gain)


def nest_has_usable_food(
    creature,
    *,
    min_satiety_gain: float = 1.0,
    min_food_ratio: float = 0.01,
    min_absolute: float = 8.0,
) -> bool:
    """
    巣の備蓄が「食事として意味がある」か。
    極端に少ない備蓄（8/5000 など）はなし扱い。
    """
    stored = nest_stored_food(creature)
    if stored <= min_absolute:
        return False

    world = getattr(creature, "world", None)
    if world is not None:
        colony = getattr(creature, "colony", None)
        if colony is not None:
            nest = world.nest_system.get_creature_nest(creature)
            if nest is not None and nest.max_food > 0:
                if stored / float(nest.max_food) < min_food_ratio:
                    return False

    return nest_feed_satiety_gain_estimate(creature) >= min_satiety_gain


def is_edible_prey(creature, target, species_names) -> bool:
    if target is None or target is creature:
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if target.species.name not in names:
        return False
    if target.alive:
        return True
    world = getattr(creature, "world", None)
    return carcass_on_field(world, target)


def is_trackable_prey(creature, target, species_names) -> bool:
    return is_edible_prey(creature, target, species_names) and is_in_vision(
        creature, target
    )


def expand_faction_species(world, colony_ids) -> tuple[str, ...]:
    """勢力 ID からそのコロニーに属する全種名を列挙（world.colony.faction_species）。"""
    if world is None:
        return ()
    faction_species = getattr(world, "faction_species", {}) or {}
    names: list[str] = []
    for cid in colony_ids or ():
        for name in faction_species.get(cid, ()):
            if name not in names:
                names.append(str(name))
    return tuple(names)


def is_hostile_target(creature, target, species_names) -> bool:
    """戦闘対象（生きている指定種のみ。死骸は対象外）。"""
    if target is None or target is creature:
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if target.species.name not in names:
        return False
    return bool(target.alive)


def is_trackable_hostile(creature, target, species_names) -> bool:
    return is_hostile_target(creature, target, species_names) and is_in_vision(
        creature, target
    )


DEFAULT_TERRITORY_RADIUS = 180.0


def resolve_colony_id(species_name: str, colony_cfg: dict | None = None) -> str:
    """種設定から勢力 ID を解決（join_species / join_colony_id 対応）。"""
    cfg = colony_cfg or {}
    cid = cfg.get("colony_id")
    if cid:
        return str(cid)
    join_cid = cfg.get("join_colony_id")
    if join_cid:
        return str(join_cid)
    join_species = cfg.get("join_species")
    if join_species:
        from src.config import config

        join_data = config.get_species(join_species) or {}
        return resolve_colony_id(join_species, join_data.get("colony", {}))
    return str(species_name)


def get_territory_radius_for_nest(world, nest) -> float:
    """巣の owner 種の colony.territory_radius（未設定時は既定 180）。"""
    if world is None or nest is None:
        return DEFAULT_TERRITORY_RADIUS
    from src.config import config

    species_data = config.get_species(nest.owner_species) or {}
    cfg = species_data.get("colony", {})
    return float(cfg.get("territory_radius", DEFAULT_TERRITORY_RADIUS))


def iter_territory_centers(nest) -> list[tuple[float, float]]:
    """テリトリー円の中心（全巣穴。穴が無いときは巣座標）。"""
    holes = getattr(nest, "holes", None) or []
    if holes:
        return [(float(h.x), float(h.y)) for h in holes]
    return [(float(nest.x), float(nest.y))]


def distance_from_nest_center(world, nest, x: float, y: float) -> float:
    """巣備蓄座標からワールド座標までの距離（レガシー）。"""
    return math.hypot(float(x) - nest.x, float(y) - nest.y)


def is_point_in_nest_territory(world, nest, x: float, y: float) -> bool:
    """いずれかの巣穴（または巣座標）を中心とするテリトリー円内か。"""
    if world is None or nest is None:
        return False
    radius = get_territory_radius_for_nest(world, nest)
    px, py = float(x), float(y)
    for cx, cy in iter_territory_centers(nest):
        if math.hypot(px - cx, py - cy) <= radius:
            return True
    return False


def is_point_in_colony_territory(world, colony_id: str, x: float, y: float) -> bool:
    """勢力のコロニー巣テリトリー内か。"""
    if world is None or not colony_id:
        return False
    nest = world.nest_system.get_colony_nest(colony_id)
    if nest is None:
        return False
    return is_point_in_nest_territory(world, nest, x, y)


def is_point_in_creature_territory(creature, x: float, y: float) -> bool:
    """個体の所属コロニーテリトリー内か（全巣穴の円の和集合）。"""
    world = getattr(creature, "world", None)
    if world is None:
        return False
    nest = world.nest_system.get_creature_nest(creature)
    if nest is None:
        return False
    return is_point_in_nest_territory(world, nest, x, y)


def is_in_creature_territory(creature, other) -> bool:
    """他個体が自分のコロニーテリトリー内にいるか。"""
    if other is None:
        return False
    ox, oy = entity_xy(other)
    return is_point_in_creature_territory(creature, ox, oy)


def find_nearest_hostile_among(creature, species_names, exclude=None):
    """視界内で最も近い敵対生体。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_hostile_target(creature, other, names):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def find_nearest_hostile_in_territory_among(creature, species_names, exclude=None):
    """テリトリー内にいる敵対生体のうち、視界内で最も近いもの。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_hostile_target(creature, other, names):
            continue
        if not is_in_creature_territory(creature, other):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def is_flee_threat(creature, other, species_names) -> bool:
    """逃走対象（指定種の生存個体）。"""
    if other is None or other is creature:
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if other.species.name not in names:
        return False
    return bool(getattr(other, "alive", True))


def find_nearest_flee_threat_among(creature, species_names, exclude=None):
    """視界内で最も近い逃走対象。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_flee_threat(creature, other, names):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def get_flee_safe_distance(creature) -> float:
    """この距離より脅威が近い間は逃走ラッチを維持する。"""
    custom = creature.traits.get("flee_safe_distance")
    if custom is not None:
        return float(custom)
    vision = max(creature.get_current_vision(), 1.0)
    return max(120.0, vision * 0.55)


def update_flee_latch(creature, threat_species) -> None:
    """視界内の脅威でラッチ ON。解除は safe 距離外まで。"""
    names = tuple(threat_species)
    if find_nearest_flee_threat_among(creature, names, exclude=creature) is not None:
        creature.flee_latch = True
        return
    if not getattr(creature, "flee_latch", False) or not creature.world:
        creature.flee_latch = False
        return
    safe = get_flee_safe_distance(creature)
    for other in creature.world.creatures:
        if other is creature or not is_flee_threat(creature, other, names):
            continue
        if distance_between(creature, other) < safe:
            return
    creature.flee_latch = False


def refresh_flee_latch_from_species(creature) -> None:
    """種定義の FleeAction から threat_species を集めてラッチを更新。"""
    if not getattr(creature, "alive", True):
        creature.flee_latch = False
        return
    threats: list[str] = []
    for action_def in creature.species.mind_data.get("actions", []):
        if action_def.get("name") != "FleeAction":
            continue
        raw = action_def.get("params", {}).get("threat_species") or ()
        threats.extend(raw)
    if threats:
        update_flee_latch(creature, tuple(dict.fromkeys(threats)))
    else:
        creature.flee_latch = False


def is_flee_latch_active(creature) -> bool:
    return bool(getattr(creature, "flee_latch", False))


def distance_to_creature_nest(creature) -> float:
    world = getattr(creature, "world", None)
    if world is None or getattr(creature, "colony", None) is None:
        return float("inf")
    return world.nest_system.distance_to_nest(creature)


def is_beyond_nest_leash(creature, leash_radius) -> bool:
    if leash_radius is None:
        return False
    return distance_to_creature_nest(creature) > float(leash_radius)


def return_toward_nest(creature, speed_multiplier: float = 1.0) -> float:
    """所属巣（最寄り巣穴）へ向かう。"""
    ns = creature.world.nest_system
    tx, ty = ns.nest_target_xy(creature)
    return move_toward_point(creature, tx, ty, speed_multiplier)


def find_nearest_edible_in_territory_among(creature, species_names, exclude=None):
    """テリトリー内の獲物／死骸のうち視界内で最も近いもの。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_edible_prey(creature, other, names):
            continue
        if not is_in_creature_territory(creature, other):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def find_nearest_edible_among(creature, species_names, exclude=None):
    """複数種のうち視界内で最も近い獲物／死骸。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude or not is_edible_prey(creature, other, names):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def find_nearest_field_carcass_among(creature, species_names, exclude=None):
    """視界内で最も近い、現場に残る死骸（生きた個体は除外）。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude:
            continue
        if other.alive or other.species.name not in names:
            continue
        if not carcass_on_field(creature.world, other):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


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


def carcass_on_field(world, target) -> bool:
    """ワールド上に存在し、まだバイオマスが残る死骸か。"""
    if world is None or target is None:
        return False
    return target in world.creatures and has_edible_carcass(target)


def is_unclaimed_carcass(world, carcass) -> bool:
    """残存バイオマスがある死骸（複数個体が同時に回収可能）。"""
    return has_edible_carcass(carcass)


def is_living_prey(target, species_name: str) -> bool:
    return target is not None and target.alive and target.species.name == species_name


def is_edible_target(creature, target, species_name: str) -> bool:
    if target is None or target is creature:
        return False
    if target.species.name != species_name:
        return False
    if target.alive:
        return True
    world = getattr(creature, "world", None)
    return carcass_on_field(world, target)


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


def _sim_dt(creature, dt: float | None = None) -> float:
    if dt is not None:
        return float(dt)
    world = getattr(creature, "world", None)
    if world is None:
        return 1.0
    return float(getattr(world, "sim_dt", 1.0))


def move_away_from(
    creature,
    target,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
) -> float:
    """脅威から離れる方向へ移動し、移動後の距離を返す。"""
    from src.systems.movement_system import MovementSystem

    position = MovementSystem._require_position(creature)
    tx, ty = entity_xy(target)
    dx = position.x - tx
    dy = position.y - ty
    dist = math.hypot(dx, dy)
    if dist > 1e-6:
        creature.wander_angle = math.degrees(math.atan2(dy, dx)) % 360
    step = creature.get_current_speed() * speed_multiplier * _sim_dt(creature, dt)
    position.x += math.cos(math.radians(creature.wander_angle)) * step
    position.y += math.sin(math.radians(creature.wander_angle)) * step
    from src.utils.position_helpers import sync_legacy_pos

    sync_legacy_pos(creature)
    return math.hypot(tx - position.x, ty - position.y)


def move_toward(
    creature,
    target,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
    min_distance: float | None = None,
) -> float:
    """ターゲット方向へ移動し、移動後の距離を返す。"""
    from src.systems.movement_system import MovementSystem

    return MovementSystem.move_toward(
        creature,
        target,
        speed_multiplier,
        _sim_dt(creature, dt),
        min_distance=min_distance,
    )


def move_toward_contact(
    creature,
    target,
    speed_multiplier: float = 1.0,
    contact_padding: float = 8.0,
    dt: float | None = None,
) -> float:
    """contact_range だけ近づき、相手の中心には入り込まない。"""
    standoff = contact_range(creature, target, contact_padding)
    return move_toward(
        creature,
        target,
        speed_multiplier,
        dt,
        min_distance=standoff,
    )


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
            cx, cy = entity_xy(carcass)
            world.return_mana_from_decomposition(
                carcass.remaining_biomass * 0.8,
                cx,
                cy,
            )
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


def try_attack_only(predator, target, attack_power: float = 1.0) -> bool:
    """攻撃のみ（殺害まで。その場では食べない）。"""
    if not target.alive:
        return False
    bite(predator, target, attack_power=attack_power)
    return not target.alive


def _remove_depleted_carcass(world, carcass) -> None:
    if world is None or carcass is None:
        return
    if carcass.remaining_biomass <= 0 and carcass in world.creatures:
        world.remove_creature(carcass)


def release_carried_carcass(carrier) -> None:
    """運搬チャンクをやめ、採取元の死骸にバイオマスを戻す（なければマナ還元）。"""
    colony = getattr(carrier, "colony", None)
    if colony is None or not colony.is_carrying:
        return

    chunk = float(colony.carried_biomass)
    carcass = colony.carried_carcass
    colony.carried_biomass = 0.0
    colony.carried_carcass = None
    if chunk <= 0:
        return

    world = carrier.world
    if world is None:
        return

    if carcass is not None:
        carcass.remaining_biomass += chunk
        if carcass not in world.creatures:
            carcass.world = world
            world.add_creature(carcass)
        return

    cx, cy = entity_xy(carrier)
    world.return_mana_from_decomposition(chunk * 0.65, cx, cy)


def try_pickup_carcass(carrier, carcass, contact_padding: float = 8.0) -> bool:
    """接触した死骸からチャンクを切り出して運搬する（死骸は現場に残る）。"""
    colony = getattr(carrier, "colony", None)
    if colony is None or colony.is_carrying:
        return False
    world = carrier.world
    if not has_edible_carcass(carcass):
        return False

    dist = distance_between(carrier, carcass)
    reach = contact_range(carrier, carcass, contact_padding)
    if dist > reach * 1.05:
        return False

    max_carry = get_haul_max_carry(carrier)
    if max_carry <= 0:
        return False

    chunk = min(float(carcass.remaining_biomass), max_carry)
    if chunk <= 0:
        return False

    carcass.remaining_biomass -= chunk
    colony.carried_biomass = chunk
    colony.carried_carcass = carcass

    if world is not None:
        _remove_depleted_carcass(world, carcass)

    return True


def consume_carried_biomass(predator, bite_gain: float = 1.35) -> float:
    """運搬中チャンクをその場で消費して満腹度を回復。"""
    colony = getattr(predator, "colony", None)
    if colony is None or colony.carried_biomass <= 0:
        return 0.0

    base_size = float(predator.traits.get("base_size", 9.0))
    bite_gain = float(bite_gain)
    amount = min(
        colony.carried_biomass * 0.45,
        base_size * bite_gain * 1.6,
    )
    colony.carried_biomass = max(0.0, colony.carried_biomass - amount * 0.9)

    gained = amount * bite_gain
    predator.satiety = min(predator.max_satiety, predator.satiety + gained)

    if colony.carried_biomass <= 1.0:
        leftover = colony.carried_biomass
        colony.carried_biomass = 0.0
        colony.carried_carcass = None
        world = predator.world
        if world is not None and leftover > 0:
            cx, cy = entity_xy(predator)
            world.return_mana_from_decomposition(leftover * 0.8, cx, cy)

    return gained


def find_nearest_carcass_in_vision(creature, species_name: str, exclude=None):
    """視界内の未運搬・指定種の死骸を探す。"""
    if not creature.world:
        return None

    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()

    for other in creature.world.creatures:
        if other is exclude:
            continue
        if other.species.name != species_name:
            continue
        if not has_edible_carcass(other):
            continue
        dist = distance_between(creature, other)
        if dist <= vision and dist < min_dist:
            min_dist = dist
            best = other
    return best


def wander_step(
    creature,
    angle_range: float,
    speed_multiplier: float,
    dt: float | None = None,
) -> None:
    from src.systems.movement_system import MovementSystem

    MovementSystem.wander_step(
        creature,
        angle_range,
        speed_multiplier,
        _sim_dt(creature, dt),
        getattr(creature, "world", None),
    )


def get_mana_gradient_direction(
    creature, sampling_distance: float = 60.0, angle_step: int = 45
) -> float:
    """マナ濃度が最も高い方向（度数法 0~360）を返す。"""
    if not creature.world or not creature.world.biome_noise:
        return creature.wander_angle

    best_angle = creature.wander_angle
    best_mana = -1.0

    cx, cy = entity_xy(creature)
    for angle in range(0, 360, angle_step):
        rad = math.radians(angle)
        tx = cx + math.cos(rad) * sampling_distance
        ty = cy + math.sin(rad) * sampling_distance

        tx = max(0, min(creature.world.width, tx))
        ty = max(0, min(creature.world.height, ty))

        mana_value = (
            creature.world.get_mana_density(tx, ty)
            if hasattr(creature.world, "get_mana_density")
            else creature.world.get_mana_regen_multiplier(tx, ty)
        )

        if mana_value > best_mana:
            best_mana = mana_value
            best_angle = angle

    return best_angle


def count_alive_by_species(world, species_name: str) -> int:
    """ワールド上の生存個体数（種族名で集計）。"""
    if world is None:
        return 0
    count = 0
    for other in world.creatures:
        if not getattr(other, "alive", True):
            continue
        if other.species.name != species_name:
            continue
        count += 1
    return count


def get_species_population_cap(world, species_name: str) -> int | None:
    """ワールド JSON の population_limits における種族上限。"""
    if world is None:
        return None
    getter = getattr(world, "get_population_cap", None)
    if callable(getter):
        return getter(species_name)
    limits = getattr(world, "population_limits", None) or {}
    raw = limits.get(species_name)
    if raw is None:
        return None
    cap = int(raw)
    return cap if cap > 0 else None


def is_species_at_population_cap(world, species_name: str) -> bool:
    """ワールド個体数上限に達しているか（未設定は上限なし）。"""
    cap = get_species_population_cap(world, species_name)
    if cap is None:
        return False
    return count_alive_by_species(world, species_name) >= cap


def is_at_population_cap(creature) -> bool:
    """個体の種族がワールド個体数上限に達しているか。"""
    if not creature.world:
        return False
    return is_species_at_population_cap(creature.world, creature.species.name)


def count_same_species_near(
    creature,
    x: float,
    y: float,
    radius: float,
    *,
    exclude_self: bool = True,
) -> int:
    """指定座標の半径内にいる同種（生存）の個体数。"""
    if not creature.world or radius <= 0:
        return 0

    species_name = creature.species.name
    count = 0
    for other in creature.world.creatures:
        if exclude_self and other is creature:
            continue
        if not getattr(other, "alive", True):
            continue
        if other.species.name != species_name:
            continue
        ox, oy = entity_xy(other)
        if math.hypot(ox - x, oy - y) <= radius:
            count += 1
    return count


def same_species_repulsion_angle(creature, radius: float) -> float | None:
    """近傍同種から離れる方向（度数）。近傍がなければ None。"""
    if not creature.world or radius <= 0:
        return None

    cx, cy = entity_xy(creature)
    species_name = creature.species.name
    push_x = 0.0
    push_y = 0.0

    for other in creature.world.creatures:
        if other is creature or not getattr(other, "alive", True):
            continue
        if other.species.name != species_name:
            continue
        ox, oy = entity_xy(other)
        dx = cx - ox
        dy = cy - oy
        dist = math.hypot(dx, dy)
        if dist <= 1e-6 or dist > radius:
            continue
        weight = (radius - dist) / radius
        push_x += (dx / dist) * weight
        push_y += (dy / dist) * weight

    magnitude = math.hypot(push_x, push_y)
    if magnitude <= 1e-6:
        return None
    return math.degrees(math.atan2(push_y, push_x)) % 360


def get_local_mana_gradient_direction(
    creature,
    radius: float = 35.0,
    samples: int = 8,
    escape_radius: float = 96.0,
    depleted_ratio: float = 0.12,
) -> float:
    """後方互換ラッパー → ManaSystem.get_local_gradient_direction"""
    from src.systems.mana_system import ManaSystem

    if not creature.world:
        return getattr(creature, "wander_angle", random.uniform(0, 360))

    params = {
        "local_gradient_radius": radius,
        "local_gradient_samples": samples,
        "escape_radius": escape_radius,
        "depleted_ratio": depleted_ratio,
    }
    return ManaSystem.get_local_gradient_direction(creature, creature.world, params)
