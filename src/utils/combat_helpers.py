"""攻撃・捕食・死骸・運搬チャンクの処理。"""

from src.utils.geo_helpers import distance_between
from src.utils.movement_helpers import contact_range
from src.utils.nutrition_helpers import get_haul_max_carry
from src.utils.position_helpers import entity_xy
from src.utils.target_helpers import has_edible_carcass

def hp_ratio(creature) -> float:
    """HPの割合（0〜1）"""
    if creature.max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.hp / creature.max_hp))

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
            world.mana_layer.return_from_decomposition(
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
    world.mana_layer.return_from_decomposition(chunk * 0.65, cx, cy)

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
            world.mana_layer.return_from_decomposition(leftover * 0.8, cx, cy)

    return gained
