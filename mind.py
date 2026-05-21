from abc import ABC, abstractmethod
import random


class Mind(ABC):
    @abstractmethod
    def decide_next_action(self, creature):
        pass


class UtilityMind(Mind):
    """Utility AI方式 + 詳細デバッグ"""
    
    def __init__(self, mind_data: dict):
        self.action_defs = mind_data.get("actions", [])

    def decide_next_action(self, creature):
        # print(f"\n[Mind] {creature.species.name} (Age:{creature.age} Energy:{creature.energy:.1f}/{creature.traits.get('max_energy')})")

        # 現在のActionが継続中かチェック
        if creature.current_action and not creature.current_action.is_completed():
            print(f"  → 継続中: {creature.current_action.__class__.__name__}")
            return creature.current_action

        best_action = None
        best_score = -1.0

        for action_def in self.action_defs:
            action_name = action_def["name"]
            params = action_def.get("params", {})
            weight = action_def.get("weight", 1.0)

            # Actionインスタンス作成
            if action_name == "WanderAction":
                from actions import WanderAction
                action = WanderAction(**params)
            elif action_name == "IdleAction":
                from actions import IdleAction
                action = IdleAction(**params)
            elif action_name == "ChaseAction":
                from actions import ChaseAction
                action = ChaseAction(**params)
            else:
                continue

            utility = action.calculate_utility(creature)
            score = utility * weight

            # print(f"  → {action_name:12s} | Utility: {utility:.3f} × Weight: {weight:.2f} = Score: {score:.3f}")

            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            from actions import WanderAction
            best_action = WanderAction()

        # print(f"  ★ 最終選択: {best_action.__class__.__name__} (Score: {best_score:.3f})")
        return best_action