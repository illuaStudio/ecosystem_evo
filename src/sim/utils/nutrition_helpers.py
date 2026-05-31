"""満腹度・飢餓・巣の食料判定。"""

from src.sim.utils.target_helpers import has_edible_carcass

def satiety_ratio(creature) -> float:
    """満腹度の割合（0〜1）"""
    if creature.max_satiety <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.satiety / creature.max_satiety))

def hunger_ratio(creature) -> float:
    """空腹度（0=満腹, 1=空腹）。"""
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

def get_satiety_feed_below(creature) -> float:
    """満腹度比率がこれ以下で巣食事ラッチを開始（未指定時は飢餓閾値と同じ）。"""
    traits = creature.traits
    if "satiety_feed_below" in traits:
        return float(traits["satiety_feed_below"])
    return get_satiety_hungry_below(creature)

def get_satiety_full_above(creature) -> float:
    """満腹度比率の目標上限（巣での食事停止・HUD「満腹」表示）。"""
    return float(creature.traits.get("satiety_full_above", 0.85))

def satiety_feed_target(creature) -> float:
    """巣食事の満腹度目標（絶対値）。"""
    return get_satiety_full_above(creature) * creature.max_satiety

def satiety_room_until_feed_target(creature) -> float:
    """巣で satiety_full_above まで回復できる余地。"""
    return max(0.0, satiety_feed_target(creature) - creature.satiety)


def nest_feed_completion_slack(creature) -> float:
    """代謝で満腹目標まで届かない距離（絶対値）。"""
    metabolism = float(creature.traits.get("metabolism_per_tick", 0.5))
    target = satiety_feed_target(creature)
    return max(metabolism * 2.5, target * 0.003)


def nest_feed_completion_ratio_slack(creature) -> float:
    """満腹度比率での完了余裕（max_satiety の個体差・代謝を吸収）。"""
    metabolism = float(creature.traits.get("metabolism_per_tick", 0.5))
    max_sat = max(float(creature.max_satiety), 1.0)
    return max(metabolism * 3.0 / max_sat, 0.009)


def is_nest_feed_satisfied(creature) -> bool:
    """巣食事の目的を達成済み（目標到達、または代謝で届かない距離）。"""
    sat = satiety_ratio(creature)
    full = get_satiety_full_above(creature)
    if sat >= full:
        return True
    # HUD 表示（整数%）と一致させる
    if round(sat * 100) >= round(full * 100):
        return True

    target = satiety_feed_target(creature)
    if creature.satiety >= target:
        return True
    if creature.satiety >= target - nest_feed_completion_slack(creature):
        return True
    return sat >= full - nest_feed_completion_ratio_slack(creature)


def needs_nest_feed(creature) -> bool:
    """巣食事の余地がある（full_above 未満）。"""
    return not is_nest_feed_satisfied(creature)

def get_nutrition_state(creature) -> str:
    sat = satiety_ratio(creature)
    if sat <= get_satiety_hungry_below(creature):
        return NutritionState.HUNGRY
    if is_nest_feed_satisfied(creature):
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
    if sat <= get_satiety_feed_below(creature):
        creature.nutrition_recovery = True
    elif is_nest_feed_satisfied(creature):
        creature.nutrition_recovery = False

def needs_self_feed(creature) -> bool:
    """自己給餌モード（feed_below 以下で開始、satiety_full_above まで維持）。"""
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
    """HUD 用: インベントリ状態（後方互換名）。"""
    from src.sim.utils.inventory_helpers import format_inventory_status

    return format_inventory_status(creature)


def get_haul_max_carry(creature, default: float = 50.0) -> float:
    """先頭スロットのバイオマス上限（後方互換）。"""
    from src.sim.utils.inventory_helpers import get_haul_max_carry as _max

    return _max(creature, default=default)

def nest_stored_food(creature, default: float = 0.0) -> float:
    from src.sim.utils.world_object_helpers import (
        get_creature_colony_root,
        get_creature_nest_parent_ids,
        parent_stored_food,
    )

    if get_creature_nest_parent_ids(creature):
        return parent_stored_food(creature, default=default)

    root = get_creature_colony_root(creature)
    if root is None or root.storage is None:
        return default
    return float(root.storage.stored_food)

def nest_has_food(creature, min_food: float = 8.0) -> bool:
    """stored_food が絶対量の下限を超えるか（粗い判定）。"""
    return nest_stored_food(creature) > min_food


def nest_has_usable_food(creature) -> bool:
    """巣の備蓄が食事に使えるか（備蓄 > 0 かつ満腹目標まで余地あり）。"""
    if nest_stored_food(creature) <= 0:
        return False
    return satiety_room_until_feed_target(creature) > 0


def get_nest_feed_config(creature) -> dict[str, float]:
    """種 JSON の nest_feed（feed_per_tick, bite_gain）を返す。"""
    nf = getattr(creature.species, "nest_feed", None)
    if nf is None:
        raise KeyError(f"species {creature.species.name}: nest_feed block required")
    return nf


def nest_feed_satiety_gain_estimate(creature) -> float:
    """次の1ティックで巣から得られる満腹度の見積もり。"""
    cfg = get_nest_feed_config(creature)
    feed_per_tick = cfg["feed_per_tick"]
    bite_gain = cfg["bite_gain"]
    world = getattr(creature, "world", None)
    if world is None:
        return 0.0
    colony = getattr(creature, "colony", None)
    if colony is None:
        return 0.0
    from src.sim.utils.world_object_helpers import get_creature_colony_root

    root = get_creature_colony_root(creature)
    if root is None or root.storage is None or root.storage.stored_food <= 0:
        return 0.0

    max_sat = float(creature.max_satiety)
    if float(creature.satiety) >= max_sat:
        return 0.0

    take = min(root.storage.stored_food, float(feed_per_tick))
    gain = take * float(bite_gain)
    room = max_sat - float(creature.satiety)
    return min(gain, room)
