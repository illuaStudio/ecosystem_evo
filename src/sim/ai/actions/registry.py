"""行動クラス名 → Action クラスのレジストリ（sim + game）。"""
from __future__ import annotations

from typing import Dict, Type

from src.sim.ai.actions.base import Action

ACTION_BY_NAME: Dict[str, Type[Action]] = {}


def register_action(name: str, action_cls: Type[Action]) -> None:
    ACTION_BY_NAME[name] = action_cls


def register_action_aliases(mapping: Dict[str, Type[Action]]) -> None:
    ACTION_BY_NAME.update(mapping)
