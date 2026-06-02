"""ゲーム層: SimBridge が委譲するコロニー固有コマンド。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.game.caste_helpers import creature_matches_affiliation_caste, normalize_caste
from src.game.shelter_helpers import (
    _restrict_mind_for_shelter,
    resolve_creature_shelter,
)
from src.sim.commands import (
    EnterCreatureShelter,
    SetAffiliationCasteMind,
    SimCommandResult,
)
from src.sim.shelter.helpers import enter_creature_shelter as attach_creature_shelter_ref

if TYPE_CHECKING:
    from src.sim.bridge import SimBridge


def _apply_mind(creature, actions: tuple[dict, ...], mode: str) -> bool:
    mind = getattr(creature, "mind", None)
    if mind is None or not hasattr(mind, "action_defs"):
        return False
    if mode == "reset":
        mind.reset_to_base()
    elif mode == "merge":
        mind.merge_action_defs(list(actions))
    else:
        mind.set_action_defs(list(actions))
    creature.current_action = None
    return True


def set_affiliation_caste_mind(bridge: "SimBridge", cmd: SetAffiliationCasteMind) -> SimCommandResult:
    caste = normalize_caste(cmd.caste) if isinstance(cmd.caste, str) else cmd.caste
    if caste is None:
        return SimCommandResult(
            False,
            "SetAffiliationCasteMind",
            f"unknown caste={cmd.caste!r}",
        )

    matched: list[Any] = []
    for creature in bridge.world.creatures:
        if not creature_matches_affiliation_caste(creature, cmd.affiliation_id, caste):
            continue
        if _apply_mind(creature, cmd.actions, cmd.mode):
            matched.append(creature)
    if not matched:
        return SimCommandResult(
            False,
            "SetAffiliationCasteMind",
            f"no creatures for colony={cmd.affiliation_id} caste={caste}",
        )
    return SimCommandResult(
        True,
        "SetAffiliationCasteMind",
        creatures=matched,
        count=len(matched),
    )


def enter_creature_shelter(bridge: "SimBridge", cmd: EnterCreatureShelter) -> SimCommandResult:
    creature = bridge.creature_by_id(cmd.creature_id)
    if creature is None:
        return SimCommandResult(
            False,
            "EnterCreatureShelter",
            f"creature id={cmd.creature_id} not found",
        )

    ref = resolve_creature_shelter(creature)
    if ref is None:
        return SimCommandResult(False, "EnterCreatureShelter", "no shelter ref")

    creature.position.x = ref.x
    creature.position.y = ref.y
    creature.pos[0] = ref.x
    creature.pos[1] = ref.y
    attach_creature_shelter_ref(creature, ref)
    _restrict_mind_for_shelter(creature)
    return SimCommandResult(
        True,
        "EnterCreatureShelter",
        creature=creature,
        creatures=[creature],
        count=1,
    )


GAME_BRIDGE_HOOKS = {
    "SetAffiliationCasteMind": set_affiliation_caste_mind,
    "EnterCreatureShelter": enter_creature_shelter,
}
