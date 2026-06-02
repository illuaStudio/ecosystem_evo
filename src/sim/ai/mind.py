from abc import ABC, abstractmethod

from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.ai.action_config import expand_action_params
from src.sim.ai.actions.registry import ACTION_BY_NAME

_DEFAULT_FALLBACK_ACTION = "IdleLocomotionAction"


class Mind(ABC):
    @abstractmethod
    def decide_next_action(self, creature):
        pass


class UtilityMind(Mind):
    """Utility AI方式 + 詳細デバッグ"""

    def __init__(self, mind_data: dict):
        self._base_action_defs = list(mind_data.get("actions", []))
        self.action_defs = list(self._base_action_defs)
        self._fallback_action_name = str(
            mind_data.get("fallback_action", _DEFAULT_FALLBACK_ACTION)
        )
        raw_fb_params = mind_data.get("fallback_params")
        self._fallback_params = dict(raw_fb_params) if raw_fb_params else None

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

    def _fallback_action(self, creature):
        """有効 utility が無いときのフォールバック。"""
        name = self._fallback_action_name
        action_cls = ACTION_BY_NAME.get(name)
        if action_cls is None:
            raise KeyError(
                f"{creature.species.name}: fallback_action {name!r} が ACTION_BY_NAME に未登録です。"
                f" 種 JSON の actions 定義、または {_DEFAULT_FALLBACK_ACTION} の登録を確認してください。"
            )
        if self._fallback_params is not None:
            raw_params = dict(self._fallback_params)
        else:
            action_def = next(
                (a for a in self.action_defs if a.get("name") == name),
                None,
            )
            raw_params = dict(action_def.get("params", {})) if action_def else {}
        params = expand_action_params(action_cls, raw_params)
        return action_cls(_use_config_only=True, **params)

    def decide_next_action(self, creature):
        current = creature.current_action
        if (
            inventory_is_loaded(creature)
            and current is not None
            and not current.is_completed()
            and type(current).continues_while_carrying()
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
            best_action = self._fallback_action(creature)

        if (
            current is not None
            and not current.is_completed()
            and type(current) is type(best_action)
            and best_score > 0.0
        ):
            return current

        return best_action
