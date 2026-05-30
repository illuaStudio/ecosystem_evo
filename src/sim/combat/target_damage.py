"""対象へのダメージ適用。"""
from __future__ import annotations

from src.sim.combat.target_ref import TargetKind, TargetRef
from src.sim.utils.colony_helpers import get_creature_colony_id
from src.sim.utils.creature_helpers import try_attack_only


def apply_damage_to_target(
    attacker,
    ref: TargetRef,
    amount: float,
    *,
    attacker_colony_id: str | None = None,
) -> float:
    """TargetRef にダメージ。実際に与えた量（creature は攻撃力そのまま、穴は nest_system 返値）。"""
    if ref is None or amount <= 0:
        return 0.0

    if ref.kind is TargetKind.CREATURE:
        prey = ref.creature
        if prey is None or not getattr(prey, "alive", False):
            return 0.0
        try_attack_only(attacker, prey, attack_power=float(amount))
        return float(amount)

    if ref.kind is TargetKind.SPAWN_NODE:
        nest, hole = ref.nest, ref.hole
        if attacker.world is None or nest is None or hole is None:
            return 0.0
        cid = attacker_colony_id or get_creature_colony_id(attacker) or ""
        dealt = attacker.world.nest_system.damage_hole(
            nest, hole, float(amount), attacker_colony_id=cid
        )
        if dealt > 0:
            from src.sim.emitters import maybe_emit_combat_from_damage

            maybe_emit_combat_from_damage(attacker.world, attacker, ref, dealt)
        return dealt

    return 0.0
