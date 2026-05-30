from abc import ABC, abstractmethod

from src.shelter.state import SHELTER_ALLOWED_ACTION_NAMES, is_creature_sheltered
from src.utils.inventory_helpers import inventory_is_loaded
from src.utils.creature_helpers import needs_self_feed
from src.ai.actions import (
    AttackHoleAction,
    ChaseAction,
    ColonyReproduceAction,
    CombatAction,
    FeedAtNestAction,
    FleeAction,
    HuntAction,
    ManaGradientWanderAction,
    ManaWanderAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
    SeekShelterAction,
    SpawnWorkerAction,
    SplitAction,
    WanderAction,
)

ACTION_BY_NAME = {
    "WanderAction": WanderAction,
    "ManaWanderAction": ManaWanderAction,
    "ManaGradientWanderAction": ManaGradientWanderAction,
    "ChaseAction": ChaseAction,
    "CombatAction": CombatAction,
    "AttackHoleAction": AttackHoleAction,
    "FleeAction": FleeAction,
    "SeekShelterAction": SeekShelterAction,
    "HuntAction": HuntAction,
    "ReturnToNestAction": ReturnToNestAction,
    "ScavengeCarriedAction": ScavengeCarriedAction,
    "FeedAtNestAction": FeedAtNestAction,
    "NestPatrolAction": NestPatrolAction,
    "ColonyReproduceAction": ColonyReproduceAction,
    "SpawnWorkerAction": SpawnWorkerAction,
    "SplitAction": SplitAction,
}


class Mind(ABC):
    @abstractmethod
    def decide_next_action(self, creature):
        pass


class UtilityMind(Mind):
    """Utility AI方式 + 詳細デバッグ"""

    def __init__(self, mind_data: dict):
        self._base_action_defs = list(mind_data.get("actions", []))
        self.action_defs = list(self._base_action_defs)

    def set_action_defs(self, action_defs: list) -> None:
        """ゲーム層から実行時に mind.actions を差し替える。"""
        self.action_defs = list(action_defs)

    def reset_to_base(self) -> None:
        """種 JSON の既定 actions に戻す。"""
        self.action_defs = list(self._base_action_defs)

    def decide_next_action(self, creature):
        colony = getattr(creature, "colony", None)
        current = creature.current_action
        if inventory_is_loaded(creature):
            # 運搬中は帰巣を維持（毎ティック再評価による Hunt 等へのチャタリング防止）
            if not needs_self_feed(creature) and isinstance(
                current, ReturnToNestAction
            ):
                return current

        best_action = None
        best_score = -1.0

        sheltered = is_creature_sheltered(creature)

        for action_def in self.action_defs:
            action_name = action_def["name"]
            if sheltered and action_name not in SHELTER_ALLOWED_ACTION_NAMES:
                continue
            params = action_def.get("params", {})
            weight = action_def.get("weight", 1.0)

            action_cls = ACTION_BY_NAME.get(action_name)
            if action_cls is None:
                continue
            action = action_cls(**params)

            utility = action.calculate_utility(creature)
            if utility <= 0.0:
                continue
            score = utility * weight

            # print(f"  → {action_name:12s} | Utility: {utility:.3f} × Weight: {weight:.2f} = Score: {score:.3f}")

            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            if sheltered:
                # 巣穴待機: 許可された行動のうち先頭を維持（徘徊しない）
                for action_def in self.action_defs:
                    name = action_def.get("name")
                    if name not in SHELTER_ALLOWED_ACTION_NAMES:
                        continue
                    action_cls = ACTION_BY_NAME.get(name)
                    if action_cls is None:
                        continue
                    best_action = action_cls(**action_def.get("params", {}))
                    break
                if best_action is None:
                    best_action = SeekShelterAction(
                        **(
                            next(
                                (
                                    a.get("params", {})
                                    for a in self.action_defs
                                    if a.get("name") == "SeekShelterAction"
                                ),
                                {},
                            )
                        )
                    )
            else:
                best_action = WanderAction()

        # 同種の行動が選ばれたら進行中インスタンスを維持（追跡ターゲット等を保持）
        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
            and best_score > 0.0
        ):
            return current

        return best_action
