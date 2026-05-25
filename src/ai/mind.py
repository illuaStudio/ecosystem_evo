from abc import ABC, abstractmethod

from src.ai.actions import (
    ChaseAction,
    FeedAtNestAction,
    HuntAction,
    ManaGradientWanderAction,
    NestPatrolAction,
    ReturnToNestAction,
    SpawnWorkerAction,
    SplitAction,
    WanderAction,
)

ACTION_BY_NAME = {
    "WanderAction": WanderAction,
    "ManaGradientWanderAction": ManaGradientWanderAction,
    "ManaWanderAction": ManaGradientWanderAction,
    "ChaseAction": ChaseAction,
    "HuntAction": HuntAction,
    "ReturnToNestAction": ReturnToNestAction,
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
            score = utility * weight

            # print(f"  → {action_name:12s} | Utility: {utility:.3f} × Weight: {weight:.2f} = Score: {score:.3f}")

            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            best_action = WanderAction()

        # 同種の行動が選ばれたら進行中インスタンスを維持（追跡ターゲット等を保持）
        current = creature.current_action
        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
        ):
            return current

        return best_action
