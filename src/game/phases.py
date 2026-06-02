"""ゲームフェーズ（開発 / 防衛 / ストーリー）の型と設定。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GamePhase(str, Enum):
    DEVELOPMENT = "development"
    DEFENSE = "defense"
    STORY = "story"


@dataclass(frozen=True)
class PhaseConfig:
    development_ticks_before_defense: int = 400
    story_ticks_before_resume: int = 90
    auto_start_defense: bool = True
    auto_resume_after_story: bool = True


def phase_config_from_dict(raw: dict | None) -> PhaseConfig:
    data = dict(raw or {})
    return PhaseConfig(
        development_ticks_before_defense=max(
            1, int(data.get("development_ticks_before_defense", 400))
        ),
        story_ticks_before_resume=max(1, int(data.get("story_ticks_before_resume", 90))),
        auto_start_defense=bool(data.get("auto_start_defense", True)),
        auto_resume_after_story=bool(data.get("auto_resume_after_story", True)),
    )
