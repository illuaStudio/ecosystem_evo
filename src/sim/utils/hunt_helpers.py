"""狩り・戦闘ターゲットの参照・検索。"""
from __future__ import annotations

from typing import Any, List, Optional


def get_hunt_target(creature: Any) -> Optional[Any]:
    """現在 HuntAction 中の獲物／死骸。該当しなければ None。"""
    action = getattr(creature, "current_action", None)
    if action is None or type(action).__name__ != "HuntAction":
        return None
    target = getattr(action, "_target", None)
    if target is None:
        return None
    return target


def get_combat_target(creature: Any) -> Optional[Any]:
    """現在 CombatAction 中の敵対個体。該当しなければ None。"""
    action = getattr(creature, "current_action", None)
    if action is None or type(action).__name__ != "CombatAction":
        return None
    target = getattr(action, "_target", None)
    if target is None:
        return None
    return target


def get_aggression_target(creature: Any) -> Optional[Any]:
    """狩りまたは戦闘で追っている対象。"""
    return get_combat_target(creature) or get_hunt_target(creature)


def find_hunters_for_prey(world: Any, prey: Any) -> List[Any]:
    """指定の獲物を HuntAction のターゲットにしている個体のリスト。"""
    if world is None or prey is None:
        return []

    hunters: List[Any] = []
    for creature in getattr(world, "creatures", []):
        if creature is prey:
            continue
        if get_hunt_target(creature) is prey:
            hunters.append(creature)
    return hunters


def find_attackers_for_target(world: Any, target: Any) -> List[Any]:
    """指定個体を HuntAction または CombatAction で狙っている個体。"""
    if world is None or target is None:
        return []

    attackers: List[Any] = []
    for creature in getattr(world, "creatures", []):
        if creature is target:
            continue
        if get_aggression_target(creature) is target:
            attackers.append(creature)
    return attackers


def describe_creature_short(creature: Any) -> str:
    """HUD 用の短い表示名。"""
    if creature is None:
        return "?"
    status = "死骸" if not getattr(creature, "alive", True) else "生体"
    return f"{creature.species.name} ({status})"
