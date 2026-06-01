"""攻撃・捕食・運搬の処理。"""

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


def try_predate(
    predator,
    target,
    attack_power: float = 1.0,
    bite_gain: float = 1.35,
) -> None:
    """接触時の捕食フロー: bite → 地面バイオマスを消費。"""
    prey_x, prey_y = entity_xy(target)
    species_name = target.species.name
    if target.alive:
        bite(predator, target, attack_power=attack_power)
    if not target.alive:
        from src.sim.utils.loot_helpers import consume_biomass_near

        consume_biomass_near(
            predator,
            prey_x,
            prey_y,
            species_name=species_name,
            bite_gain=bite_gain,
        )


def try_attack_only(predator, target, attack_power: float = 1.0) -> bool:
    """攻撃のみ（殺害まで。その場では食べない）。"""
    if not target.alive:
        return False
    bite(predator, target, attack_power=attack_power)
    return not target.alive


def release_carried_biomass(carrier) -> None:
    """インベントリ内バイオマスを地面へ戻す。"""
    from src.sim.utils.inventory_helpers import release_inventory_biomass

    release_inventory_biomass(carrier)


def try_pickup_field_biomass(carrier, pickup, contact_padding: float = 8.0) -> bool:
    """地面の field バイオマスを拾う。"""
    from src.sim.utils.loot_helpers import try_pickup_loot

    return try_pickup_loot(carrier, pickup, contact_padding=contact_padding)


def consume_carried_for_kind(predator, bite_gain: float = 1.35, *, kind: str = "biomass") -> float:
    """インベントリ内バイオマスをその場で消費。"""
    from src.sim.utils.inventory_helpers import consume_inventory_for_kind

    return consume_inventory_for_kind(predator, bite_gain=bite_gain, kind=kind)
