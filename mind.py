from abc import ABC, abstractmethod


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

            # Actionインスタンス作成
            if action_name == "WanderAction":
                from actions import WanderAction
                action = WanderAction(**params)
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

        # 同種の行動が選ばれたら進行中インスタンスを維持（追跡ターゲット等を保持）
        current = creature.current_action
        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
        ):
            return current

        return best_action