"""防衛フェーズ: ウェーブ定義の読み込み・敵スポーン・クリア判定。"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.game.game_message import GameMessage

if TYPE_CHECKING:
    from src.sim.bridge import SimBridge
    from src.sim.systems.world import World

_WAVES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "game" / "waves.json"
)


@dataclass(frozen=True)
class WaveSpawnDef:
    species: str
    count: int = 1
    interval_ticks: int = 0


@dataclass(frozen=True)
class WaveDef:
    id: str
    label: str
    story_on_clear: str
    spawns: tuple[WaveSpawnDef, ...] = ()


@dataclass
class _PendingSpawn:
    species: str
    ticks_until: int


@dataclass
class WaveDirector:
    waves: tuple[WaveDef, ...] = ()
    player_affiliation_id: str = "red_ant"
    _wave_index: int = -1
    _pending: list[_PendingSpawn] = field(default_factory=list)
    _spawned_ids: set[int] = field(default_factory=set)
    _spawn_cursor: int = 0
    _wave_active: bool = False
    _all_spawned: bool = False

    @classmethod
    def from_json(cls, path: Path | None = None, *, player_affiliation_id: str) -> "WaveDirector":
        file_path = path or _WAVES_PATH
        waves: list[WaveDef] = []
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            for raw in data.get("waves") or []:
                spawns = tuple(
                    WaveSpawnDef(
                        species=str(s.get("species", "")),
                        count=max(1, int(s.get("count", 1))),
                        interval_ticks=max(0, int(s.get("interval_ticks", 0))),
                    )
                    for s in raw.get("spawns") or []
                    if s.get("species")
                )
                if not spawns:
                    continue
                waves.append(
                    WaveDef(
                        id=str(raw.get("id", f"wave_{len(waves)}")),
                        label=str(raw.get("label", "")),
                        story_on_clear=str(raw.get("story_on_clear", "")),
                        spawns=spawns,
                    )
                )
        return cls(waves=tuple(waves), player_affiliation_id=player_affiliation_id)

    def reset(self) -> None:
        self._wave_index = -1
        self._pending.clear()
        self._spawned_ids.clear()
        self._spawn_cursor = 0
        self._wave_active = False
        self._all_spawned = False

    def abort_wave(self) -> None:
        """防衛中断（プレイヤー敗北など）。"""
        self._wave_active = False
        self._pending.clear()
        self._all_spawned = True

    @property
    def wave_index(self) -> int:
        return self._wave_index

    @property
    def wave_active(self) -> bool:
        return self._wave_active

    @property
    def current_wave(self) -> WaveDef | None:
        if self._wave_index < 0 or self._wave_index >= len(self.waves):
            return None
        return self.waves[self._wave_index]

    @property
    def wave_label(self) -> str:
        wave = self.current_wave
        return wave.label if wave is not None else ""

    def enemies_alive(self, world: "World") -> int:
        alive = 0
        for creature in getattr(world, "creatures", ()) or ():
            if id(creature) in self._spawned_ids and getattr(creature, "alive", True):
                alive += 1
        return alive

    @property
    def enemies_spawned_total(self) -> int:
        return len(self._spawned_ids)

    def begin_wave(self, wave_index: int) -> list[GameMessage]:
        self._pending.clear()
        self._spawned_ids.clear()
        self._spawn_cursor = 0
        self._all_spawned = False
        if wave_index < 0 or wave_index >= len(self.waves):
            self._wave_active = False
            self._wave_index = -1
            return []
        self._wave_index = wave_index
        self._wave_active = True
        wave = self.waves[wave_index]
        delay = 0
        for spawn_def in wave.spawns:
            for i in range(spawn_def.count):
                if i > 0:
                    delay += spawn_def.interval_ticks
                self._pending.append(_PendingSpawn(species=spawn_def.species, ticks_until=delay))
        msgs: list[GameMessage] = []
        if wave.label:
            msgs.append(
                GameMessage(
                    text=f"防衛フェーズ: {wave.label}",
                    source="phase",
                    priority=3,
                )
            )
        return msgs

    def tick(self, world: "World", bridge: "SimBridge | None") -> tuple[list[GameMessage], bool]:
        """Returns (messages, wave_cleared)."""
        if not self._wave_active or bridge is None:
            return [], False

        messages: list[GameMessage] = []

        if not self._all_spawned:
            for entry in self._pending:
                if entry.ticks_until > 0:
                    entry.ticks_until -= 1
            ready = [e for e in self._pending if e.ticks_until <= 0]
            for entry in ready:
                self._pending.remove(entry)
                creature = self._spawn_enemy(world, bridge, entry.species, self._spawn_cursor)
                self._spawn_cursor += 1
                if creature is not None:
                    self._spawned_ids.add(id(creature))
            if not self._pending:
                self._all_spawned = True

        if self._all_spawned and self.enemies_alive(world) == 0:
            self._wave_active = False
            wave = self.current_wave
            if wave is not None and wave.story_on_clear:
                messages.append(
                    GameMessage(
                        text=wave.story_on_clear,
                        source="story",
                        priority=4,
                    )
                )
            return messages, True

        return messages, False

    def _spawn_enemy(
        self,
        world: "World",
        bridge: "SimBridge",
        species: str,
        slot: int,
    ) -> Any | None:
        from src.game.command_builder import spawn_creature as bridge_spawn

        total = max(1, self.enemies_spawned_total + len(self._pending) + 1)
        x, y = _wave_spawn_xy(world, self.player_affiliation_id, slot, total)
        creature = bridge_spawn(bridge, species, x=x, y=y, source="game")
        if creature is not None:
            from src.game.command_builder import apply_spawn_profile

            apply_spawn_profile(bridge, creature)
        return creature


def _wave_spawn_xy(
    world: "World",
    player_affiliation_id: str,
    slot: int,
    total: int,
) -> tuple[float, float]:
    cx = float(world.width) * 0.5
    cy = float(world.height) * 0.5
    try:
        from src.game.colony_session import try_get_colony_orchestrator

        orch = try_get_colony_orchestrator(world)
        if orch is not None:
            root = orch.get_affiliation_root(player_affiliation_id)
            if root is not None:
                cx, cy = float(root.x), float(root.y)
    except Exception:
        pass

    angle = (2.0 * math.pi * float(slot)) / max(1.0, float(total))
    dist = 280.0
    x = cx + math.cos(angle) * dist
    y = cy + math.sin(angle) * dist
    margin = 80.0
    x = max(margin, min(float(world.width) - margin, x))
    y = max(margin, min(float(world.height) - margin, y))
    return x, y
