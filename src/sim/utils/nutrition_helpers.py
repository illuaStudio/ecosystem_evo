"""満腹度・飢餓（汎用。拠点給餌ルールは game.affiliation_feed）。"""
from src.sim.utils.target_helpers import has_edible_carcass


def satiety_ratio(creature) -> float:
    if creature.max_satiety <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.satiety / creature.max_satiety))


def hunger_ratio(creature) -> float:
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
    return float(creature.traits.get("satiety_hungry_below", 0.15))


def get_satiety_feed_below(creature) -> float:
    traits = creature.traits
    if "satiety_feed_below" in traits:
        return float(traits["satiety_feed_below"])
    return get_satiety_hungry_below(creature)


def get_satiety_full_above(creature) -> float:
    return float(creature.traits.get("satiety_full_above", 0.85))


def satiety_feed_target(creature) -> float:
    return get_satiety_full_above(creature) * creature.max_satiety


def satiety_room_until_feed_target(creature) -> float:
    return max(0.0, satiety_feed_target(creature) - creature.satiety)


def get_nutrition_state(creature) -> str:
    sat = satiety_ratio(creature)
    if sat <= get_satiety_hungry_below(creature):
        return NutritionState.HUNGRY
    if sat >= get_satiety_full_above(creature):
        return NutritionState.FULL
    return NutritionState.NORMAL


def is_hungry(creature) -> bool:
    return get_nutrition_state(creature) == NutritionState.HUNGRY


def update_nutrition_recovery(creature) -> None:
    if not getattr(creature, "alive", True):
        creature.nutrition_recovery = False
        return
    sat = satiety_ratio(creature)
    if sat <= get_satiety_feed_below(creature):
        creature.nutrition_recovery = True
    elif sat >= get_satiety_full_above(creature):
        creature.nutrition_recovery = False


def needs_self_feed(creature) -> bool:
    update_nutrition_recovery(creature)
    return bool(getattr(creature, "nutrition_recovery", False))


def is_satiated(creature) -> bool:
    return satiety_ratio(creature) >= get_satiety_full_above(creature)


def format_nutrition_status(creature) -> str:
    label = NUTRITION_LABELS[get_nutrition_state(creature)]
    if needs_self_feed(creature) and not is_hungry(creature):
        label = f"{label}・回復中"
    return f"栄養: {label} ({satiety_ratio(creature) * 100:.0f}%)"


def format_carry_status(creature) -> str | None:
    from src.sim.utils.inventory_helpers import format_inventory_status

    return format_inventory_status(creature)


def get_haul_max_carry(creature, default: float = 50.0) -> float:
    from src.sim.utils.inventory_helpers import get_haul_max_carry as _max

    return _max(creature, default=default)
