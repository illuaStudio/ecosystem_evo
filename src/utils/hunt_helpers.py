"""狩り（HuntAction）ターゲットの参照・検索。"""
from __future__ import annotations

from typing import Any, List, Optional

from src.ai.actions import HuntAction


def get_hunt_target(creature: Any) -> Optional[Any]:
    """現在 HuntAction 中の獲物／死骸。該当しなければ None。"""
    action = getattr(creature, "current_action", None)
    if not isinstance(action, HuntAction):
        return None
    target = getattr(action, "_target", None)
    if target is None:
        return None
    return target


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


def describe_creature_short(creature: Any) -> str:
    """HUD 用の短い表示名。"""
    if creature is None:
        return "?"
    status = "死骸" if not getattr(creature, "alive", True) else "生体"
    return f"{creature.species.name} ({status})"
