"""対象へのダメージ適用。"""
from __future__ import annotations

from src.sim.combat.target_ref import TargetKind, TargetRef
from src.sim.utils.affiliation_group_helpers import get_creature_affiliation_id
from src.sim.utils.creature_helpers import try_attack_only


def apply_damage_to_target(
    attacker,
    ref: TargetRef,
    amount: float,
    *,
    attacker_affiliation_id: str | None = None,
) -> float:
    """TargetRef にダメージ。実際に与えた量（creature は攻撃力そのまま、access は handler 返値）。"""
    if ref is None or amount <= 0:
        return 0.0

    if ref.kind is TargetKind.CREATURE:
        prey = ref.creature
        if prey is None or not getattr(prey, "alive", False):
            return 0.0
        try_attack_only(attacker, prey, attack_power=float(amount))
        return float(amount)

    if ref.kind is TargetKind.WORLD_OBJECT:
        access = ref.world_object
        affiliation_id = ref.affiliation_id
        if attacker.world is None or access is None or not affiliation_id:
            return 0.0
        cid = attacker_affiliation_id or get_creature_affiliation_id(attacker) or ""
        handler = getattr(attacker.world, "access_damage_handler", None)
        if handler is None:
            return 0.0
        dealt = handler(
            access,
            affiliation_id,
            float(amount),
            attacker_affiliation_id=cid,
        )
        if dealt > 0:
            from src.sim.emitters import maybe_emit_combat_from_damage

            maybe_emit_combat_from_damage(attacker.world, attacker, ref, dealt)
        return dealt

    return 0.0
