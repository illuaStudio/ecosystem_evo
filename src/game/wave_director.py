"""防衛フェーズ: ウェーブ定義の読み込み・敵スポーン・クリア判定。

敵は破壊可能な敵巣穴と、Sim のスポーンエミッター（ON で初回バースト＋維持補充）から湧く。
"""
from __future__ import annotations

import json
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
class WaveHoleDef:
    """巣穴1つ分: 座標・耐久・スポーン種／上限は 1:1。"""

    x: float
    y: float
    species: str = "invader_ant"
    budget: int = 1
    hole_max_hp: float = 180.0
    max_alive: int = 12
    spawn_interval_ticks: int = 20
    spawn_burst_size: int = 8
    initial_burst_size: int | None = None
    spawn_radius: float = 48.0


@dataclass(frozen=True)
class WaveNestDef:
    """複数穴のグループ（各穴の性質は holes 内で個別指定）。"""

    holes: tuple[WaveHoleDef, ...] = ()


WaveNestHoleDef = WaveHoleDef


@dataclass(frozen=True)
class WaveDef:
    id: str
    label: str
    story_on_clear: str
    nests: tuple[WaveNestDef, ...] = ()


@dataclass
class WaveDirector:
    waves: tuple[WaveDef, ...] = ()
    player_affiliation_id: str = "red_ant"
    _wave_index: int = -1
    _spawned_ids: set[int] = field(default_factory=set)
    _wave_active: bool = False
    _all_spawned: bool = False
    _nests_ready: bool = False
    _spawners_enabled: bool = False
    _holes: list[str] = field(default_factory=list)
    _emitter_ids: list[str] = field(default_factory=list)
    _spawner_root_ids: list[str] = field(default_factory=list)
    _burst_announced: bool = False
    _profile_applied_ids: set[int] = field(default_factory=set)

    @staticmethod
    def _parse_hole_species_budget(merged: dict[str, Any]) -> tuple[str, int] | None:
        species = str(merged.get("species", "")).strip()
        budget_raw = merged.get("budget", merged.get("count"))
        if not species:
            legacy = merged.get("spawns") or []
            if legacy and isinstance(legacy[0], dict):
                first = legacy[0]
                species = str(first.get("species", "")).strip()
                if budget_raw is None:
                    budget_raw = first.get("budget", first.get("count"))
        if not species:
            return None
        return species, max(0, int(budget_raw if budget_raw is not None else 0))

    @staticmethod
    def _parse_hole(raw: dict[str, Any]) -> WaveHoleDef | None:
        merged = dict(raw)
        parsed = WaveDirector._parse_hole_species_budget(merged)
        if parsed is None:
            return None
        species, budget = parsed
        max_alive = max(0, int(merged.get("max_alive", 12)))
        burst = max(1, int(merged.get("spawn_burst_size", max_alive or 8)))
        raw_initial = merged.get("initial_burst_size")
        initial_burst = (
            max(0, int(raw_initial)) if raw_initial is not None else None
        )
        return WaveHoleDef(
            x=float(merged.get("x", 0.0)),
            y=float(merged.get("y", 0.0)),
            species=species,
            budget=budget,
            hole_max_hp=float(merged.get("hole_max_hp", 180.0)),
            max_alive=max_alive,
            spawn_interval_ticks=max(0, int(merged.get("spawn_interval_ticks", 20))),
            spawn_burst_size=burst,
            initial_burst_size=initial_burst,
            spawn_radius=max(0.0, float(merged.get("spawn_radius", 48.0))),
        )

    @classmethod
    def from_json(
        cls,
        path: Path | None = None,
        *,
        player_affiliation_id: str,
    ) -> "WaveDirector":
        file_path = path or _WAVES_PATH
        waves: list[WaveDef] = []
        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            for raw in data.get("waves") or []:
                nests: list[WaveNestDef] = []
                for nest_raw in raw.get("nests") or []:
                    holes_list: list[WaveHoleDef] = []
                    for h in nest_raw.get("holes") or []:
                        if not isinstance(h, dict):
                            continue
                        hole = cls._parse_hole(h)
                        if hole is not None:
                            holes_list.append(hole)
                    if holes_list:
                        nests.append(WaveNestDef(holes=tuple(holes_list)))
                if not nests:
                    continue
                waves.append(
                    WaveDef(
                        id=str(raw.get("id", f"wave_{len(waves)}")),
                        label=str(raw.get("label", "")),
                        story_on_clear=str(raw.get("story_on_clear", "")),
                        nests=tuple(nests),
                    )
                )
        return cls(
            waves=tuple(waves),
            player_affiliation_id=player_affiliation_id,
        )

    def reset(self) -> None:
        self._wave_index = -1
        self._spawned_ids.clear()
        self._wave_active = False
        self._all_spawned = False
        self._nests_ready = False
        self._spawners_enabled = False
        self._burst_announced = False
        self._profile_applied_ids.clear()
        self._holes.clear()
        self._emitter_ids.clear()
        self._spawner_root_ids.clear()

    def abort_wave(self, world: "World | None" = None, bridge: "SimBridge | None" = None) -> None:
        if world is not None:
            if bridge is not None:
                self._disable_wave_spawners(bridge)
            self._teardown_wave_objects(world)
        self._wave_active = False
        self._all_spawned = True
        self._nests_ready = False
        self._spawners_enabled = False
        self._holes.clear()
        self._emitter_ids.clear()
        self._spawner_root_ids.clear()

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
        self._sync_from_spawners(world)
        alive = 0
        for creature in getattr(world, "creatures", ()) or ():
            if id(creature) in self._spawned_ids and getattr(creature, "alive", True):
                alive += 1
        return alive

    @property
    def enemies_spawned_total(self) -> int:
        return len(self._spawned_ids)

    def begin_wave(self, wave_index: int) -> list[GameMessage]:
        self._spawned_ids.clear()
        self._all_spawned = False
        self._nests_ready = False
        self._spawners_enabled = False
        self._burst_announced = False
        self._profile_applied_ids.clear()
        self._holes.clear()
        self._emitter_ids.clear()
        self._spawner_root_ids.clear()
        if wave_index < 0 or wave_index >= len(self.waves):
            self._wave_active = False
            self._wave_index = -1
            return []
        self._wave_index = wave_index
        self._wave_active = True
        wave = self.waves[wave_index]
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
        if not self._wave_active or bridge is None:
            return [], False

        messages: list[GameMessage] = []

        if not self._nests_ready:
            self._ensure_nests(world, bridge)

        if not self._spawners_enabled:
            messages.extend(self._activate_wave_spawners(world, bridge))

        self._sync_from_spawners(world)

        if self._all_holes_destroyed(world):
            self._disable_wave_spawners(bridge)
            self._all_spawned = True

        if not self._all_spawned and not world.spawn_system.any_enabled_emitter_has_budget():
            self._all_spawned = True

        if self._all_spawned and self.enemies_alive(world) == 0 and self._all_holes_destroyed(world):
            self._disable_wave_spawners(bridge)
            self._teardown_wave_objects(world)
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

    def _spawn_config_for_hole(
        self, hole: WaveHoleDef, *, species: str, lifetime_budget: int
    ) -> dict[str, Any]:
        burst = hole.initial_burst_size
        if burst is None:
            burst = hole.max_alive if hole.max_alive > 0 else hole.spawn_burst_size
        radius = max(0.0, float(hole.spawn_radius))
        spawn_at_center = radius <= 0.0
        return {
            "mode": "point",
            "species_pool": [species],
            "target_population": max(0, hole.max_alive),
            "initial_burst_count": max(0, int(burst)),
            "lifetime_budget": int(lifetime_budget),
            "replenish_batch_size": max(1, hole.spawn_burst_size),
            "replenish_cooldown_ticks": max(0, hole.spawn_interval_ticks),
            "spawn_rate_per_dt": 0.0,
            "max_spawns_per_tick": max(1, hole.spawn_burst_size),
            "start_trigger": "on_enable",
            "enabled_at_load": False,
            "spawn_at_center": spawn_at_center,
            "use_biome_weight": False,
            "nest_exclusion_radius": 0.0,
            "radius": radius if radius > 0.0 else 16.0,
            "creature_spawn_source": "game",
        }

    def _ensure_nests(self, world: "World", bridge: "SimBridge") -> None:
        wave = self.current_wave
        if wave is None:
            self._nests_ready = True
            self._all_spawned = True
            return

        self._teardown_wave_objects(world)
        self._holes.clear()
        self._emitter_ids.clear()
        self._spawner_root_ids.clear()

        from src.game.command_builder import place_spawn_emitter

        for nest_idx, nest in enumerate(wave.nests):
            for hole_idx, hole in enumerate(nest.holes):
                lifetime_budget = max(1, int(hole.budget))

                root_id = f"enemy_wave_{wave.id}_n{nest_idx}_h{hole_idx}"
                world.compound_system.ensure_root(
                    root_id,
                    float(hole.x),
                    float(hole.y),
                    type_ref="enemy_nest_site",
                    max_mass=1.0,
                    stored_mass=0.0,
                    compound_profile="generic",
                )
                self._spawner_root_ids.append(root_id)
                access = world.compound_system.add_access_point(
                    root_id,
                    float(hole.x),
                    float(hole.y),
                    type_ref="enemy_nest_hole",
                    max_hp=float(hole.hole_max_hp),
                    shelter=False,
                    deposit_access=False,
                    withdraw_access=False,
                )
                if access is not None:
                    self._holes.append(access.id)

                emitter_id = f"{root_id}_emitter"
                place_spawn_emitter(
                    bridge,
                    emitter_id,
                    float(hole.x),
                    float(hole.y),
                    self._spawn_config_for_hole(
                        hole,
                        species=hole.species,
                        lifetime_budget=lifetime_budget,
                    ),
                    label=f"wave_{wave.id}_spawner",
                )
                self._emitter_ids.append(emitter_id)

        self._nests_ready = True

    def _activate_wave_spawners(
        self, world: "World", bridge: "SimBridge"
    ) -> list[GameMessage]:
        from src.game.command_builder import set_spawn_emitter_enabled

        burst_total = 0
        for emitter_id in self._emitter_ids:
            burst_total += set_spawn_emitter_enabled(bridge, emitter_id, True)

        self._spawners_enabled = True
        self._sync_from_spawners(world)
        self._apply_spawn_profiles(bridge)

        messages: list[GameMessage] = []
        if burst_total > 0 and not self._burst_announced:
            self._burst_announced = True
            messages.append(
                GameMessage(
                    text=f"敵の巣穴から侵入蟻が一気に湧き出した（{burst_total} 匹）",
                    source="phase",
                    priority=4,
                )
            )
        return messages

    def _disable_wave_spawners(self, bridge: "SimBridge") -> None:
        from src.game.command_builder import set_spawn_emitter_enabled

        for emitter_id in self._emitter_ids:
            set_spawn_emitter_enabled(bridge, emitter_id, False)

    def _sync_from_spawners(self, world: "World") -> None:
        world.spawn_system.sync_tracked_alive()
        ids: set[int] = set()
        for eid in self._emitter_ids:
            ids.update(world.spawn_system.tracked_creature_ids(eid))
        self._spawned_ids = ids

    def _apply_spawn_profiles(self, bridge: "SimBridge") -> None:
        from src.game.command_builder import apply_spawn_profile

        for cid in list(self._spawned_ids):
            if cid in self._profile_applied_ids:
                continue
            creature = bridge.creature_by_id(cid)
            if creature is None:
                continue
            apply_spawn_profile(bridge, creature)
            self._profile_applied_ids.add(cid)

    def _teardown_wave_objects(self, world: "World") -> None:
        cs = world.compound_system
        for hid in list(self._holes):
            cs.remove_access_point(hid)
        self._holes.clear()
        ws = world.world_object_system
        for emitter_id in list(self._emitter_ids):
            ws.remove_instance(emitter_id)
        for root_id in list(self._spawner_root_ids):
            for child in list(ws.get_children(root_id)):
                cs.remove_access_point(child.id)
            ws.objects.pop(root_id, None)
            ws._children.pop(root_id, None)
        self._emitter_ids.clear()
        self._spawner_root_ids.clear()
        world.spawn_system.rebuild_from_world_objects()

    def _all_holes_destroyed(self, world: "World") -> bool:
        if not self._holes:
            return True
        ws = world.world_object_system
        for hid in self._holes:
            obj = ws.get(hid)
            if obj is not None and not obj.is_destroyed:
                return False
        return True

    def debug_exhaust_budgets(self) -> None:
        self._all_spawned = True

    def debug_destroy_all_holes(self, world: "World") -> None:
        self._teardown_wave_objects(world)
