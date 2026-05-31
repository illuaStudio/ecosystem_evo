from abc import ABC, abstractmethod

from src.sim.shelter.state import SHELTER_ALLOWED_ACTION_NAMES, is_creature_sheltered
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.creature_helpers import needs_self_feed
from src.sim.ai.actions import ACTION_BY_NAME, ReturnToNestAction, WanderAction


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
        """実行時に mind.actions を差し替える（SimBridge 経由）。"""
        self.action_defs = list(action_defs)

    def merge_action_defs(self, extra_defs: list) -> None:
        """既存 actions に不足分だけ追加（名前で重複排除）。"""
        existing = {a.get("name") for a in self.action_defs}
        merged = list(self.action_defs)
        for action_def in extra_defs:
            name = action_def.get("name")
            if name and name not in existing:
                merged.append(dict(action_def))
                existing.add(name)
        self.action_defs = merged

    def reset_to_base(self) -> None:
        """種 JSON の既定 actions に戻す。"""
        self.action_defs = list(self._base_action_defs)

    def decide_next_action(self, creature):
        colony = getattr(creature, "colony", None)
        current = creature.current_action
        if inventory_is_loaded(creature):
            if not needs_self_feed(creature) and isinstance(current, ReturnToNestAction):
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
            source = f"{creature.species.name}/{action_name}"
            action = action_cls.from_config(params, source=source)

            utility = action.calculate_utility(creature)
            if utility <= 0.0:
                continue
            score = utility * weight

            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            if sheltered:
                for action_def in self.action_defs:
                    name = action_def.get("name")
                    if name not in SHELTER_ALLOWED_ACTION_NAMES:
                        continue
                    action_cls = ACTION_BY_NAME.get(name)
                    if action_cls is None:
                        continue
                    best_action = action_cls.from_config(
                        action_def.get("params", {}),
                        source=f"{creature.species.name}/{name}",
                    )
                    break
                if best_action is None:
                    raise KeyError(
                        f"{creature.species.name}: 避難中だが許可された行動が未定義です"
                    )
            else:
                wander_def = next(
                    (a for a in self.action_defs if a.get("name") == "WanderAction"),
                    None,
                )
                if wander_def is None:
                    raise KeyError(
                        f"{creature.species.name}: フォールバック用 WanderAction が未定義です"
                    )
                best_action = WanderAction.from_config(
                    wander_def.get("params", {}),
                    source=f"{creature.species.name}/WanderAction",
                )

        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
            and best_score > 0.0
        ):
            return current

        return best_action
