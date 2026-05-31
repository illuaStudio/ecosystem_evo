"""攻撃・捕食・死骸・運搬チャンクの処理。"""

from src.sim.utils.position_helpers import entity_xy

def hp_ratio(creature) -> float:
    """HPの割合（0〜1）"""
    if creature.max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, creature.hp / creature.max_hp))

def bite(predator, prey, attack_power: float = 1.0) -> float:
    """生きている獲物に噛みつきHPダメージを与える。与えたダメージ量を返す。"""
    from src.sim.shelter.state import is_creature_sheltered

    if not prey.alive or is_creature_sheltered(prey):
        return 0.0

    damage = float(attack_power) * 12.0
    prey.hp -= damage

    if damage > 0 and predator.world is not None:
        from src.sim.emitters import emit_combat_started_creature

        emit_combat_started_creature(predator.world, predator, prey)

    if prey.hp <= 0:
        prey.become_corpse(cause="hp")

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
    """インベントリ内バイオマスをやめる（後方互換名）。"""
    from src.sim.utils.inventory_helpers import release_inventory_biomass

    release_inventory_biomass(carrier)


def try_pickup_carcass(carrier, carcass, contact_padding: float = 8.0) -> bool:
    """接触した死骸からチャンクを切り出す（後方互換名）。"""
    from src.sim.utils.inventory_helpers import try_pickup_carcass as _pickup

    return _pickup(carrier, carcass, contact_padding=contact_padding)


def consume_carried_biomass(predator, bite_gain: float = 1.35) -> float:
    """インベントリ内バイオマスをその場で消費（後方互換名）。"""
    from src.sim.utils.inventory_helpers import consume_inventory_biomass

    return consume_inventory_biomass(predator, bite_gain=bite_gain)
