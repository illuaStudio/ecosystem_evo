from abc import ABC, abstractmethod

from src.utils.creature_helpers import needs_self_feed
from src.ai.actions import (
    AttackHoleAction,
    ChaseAction,
    CombatAction,
    FeedAtNestAction,
    FleeAction,
    HuntAction,
    ManaGradientWanderAction,
    ManaWanderAction,
    NestPatrolAction,
    ReturnToNestAction,
    ScavengeCarriedAction,
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
    "HuntAction": HuntAction,
    "ReturnToNestAction": ReturnToNestAction,
    "ScavengeCarriedAction": ScavengeCarriedAction,
    "FeedAtNestAction": FeedAtNestAction,
    "NestPatrolAction": NestPatrolAction,
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
        self.action_defs = mind_data.get("actions", [])

    def decide_next_action(self, creature):
        colony = getattr(creature, "colony", None)
        current = creature.current_action
        if colony is not None and colony.is_carrying:
            # 運搬中は帰巣を維持（毎ティック再評価による Hunt 等へのチャタリング防止）
            if not needs_self_feed(creature) and isinstance(
                current, ReturnToNestAction
            ):
                return current

        best_action = None
        best_score = -1.0

        for action_def in self.action_defs:
            action_name = action_def["name"]
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
            best_action = WanderAction()

        # 同種の行動が選ばれたら進行中インスタンスを維持（追跡ターゲット等を保持）
        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
        ):
            return current

        return best_action
