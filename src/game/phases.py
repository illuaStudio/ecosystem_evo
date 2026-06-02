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
    cycle_waves: bool = True
    story_on_defeat: str = "コロニーの拠点がすべて失われました。開発フェーズに戻り、再建を始めましょう。"
    min_soldiers_before_defense: int = 3


def phase_config_from_dict(raw: dict | None) -> PhaseConfig:
    data = dict(raw or {})
    return PhaseConfig(
        development_ticks_before_defense=max(
            1, int(data.get("development_ticks_before_defense", 400))
        ),
        story_ticks_before_resume=max(1, int(data.get("story_ticks_before_resume", 90))),
        auto_start_defense=bool(data.get("auto_start_defense", True)),
        auto_resume_after_story=bool(data.get("auto_resume_after_story", True)),
        cycle_waves=bool(data.get("cycle_waves", True)),
        story_on_defeat=str(
            data.get(
                "story_on_defeat",
                "コロニーの拠点がすべて失われました。開発フェーズに戻り、再建を始めましょう。",
            )
        ),
        min_soldiers_before_defense=max(0, int(data.get("min_soldiers_before_defense", 3))),
    )
