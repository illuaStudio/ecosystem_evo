"""防衛フェーズ: ウェーブ定義の読み込み・敵スポーン・クリア判定。

敵は「空中スポーン」ではなく、破壊可能な敵巣穴（compound access）から湧く。
巣穴（穴=access）がすべて破壊され、かつ敵が残っていなければウェーブクリア。
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
class WaveNestSpawnDef:
    species: str
    budget: int = 1


@dataclass(frozen=True)
class WaveNestHoleDef:
    x: float
    y: float


@dataclass(frozen=True)
class WaveNestDef:
    holes: tuple[WaveNestHoleDef, ...] = ()
    hole_max_hp: float = 180.0
    max_alive: int = 12
    spawn_interval_ticks: int = 20
    spawn_burst_size: int = 8
    # First pulse spawns up to this many (defaults to max_alive when omitted in JSON).
    initial_burst_size: int | None = None
    spawns: tuple[WaveNestSpawnDef, ...] = ()


@dataclass(frozen=True)
class WaveDef:
    id: str
    label: str
    story_on_clear: str
    nests: tuple[WaveNestDef, ...] = ()


@dataclass
class _NestSpawnState:
    budgets: dict[str, int] = field(default_factory=dict)
    spawn_cursor: int = 0
    spawn_cooldown: int = 0
    initial_burst_done: bool = False

    def remaining_budget(self) -> int:
        return int(sum(max(0, int(v)) for v in self.budgets.values()))


@dataclass
class WaveDirector:
    waves: tuple[WaveDef, ...] = ()
    player_affiliation_id: str = "red_ant"
    _wave_index: int = -1
    _spawned_ids: set[int] = field(default_factory=set)
    _wave_active: bool = False
    _all_spawned: bool = False
    _nests_ready: bool = False
    _holes: list[str] = field(default_factory=list)
    _spawner_root_ids: list[str] = field(default_factory=list)
    _nest_states: list[_NestSpawnState] = field(default_factory=list)
    _burst_announced: bool = False

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
                    holes = tuple(
                        WaveNestHoleDef(
                            x=float(h.get("x", 0.0)),
                            y=float(h.get("y", 0.0)),
                        )
                        for h in (nest_raw.get("holes") or [])
                        if h is not None
                    )
                    spawns = tuple(
                        WaveNestSpawnDef(
                            species=str(s.get("species", "")),
                            budget=max(0, int(s.get("budget", s.get("count", 0)))),
                        )
                        for s in (nest_raw.get("spawns") or [])
                        if s.get("species")
                    )
                    if not holes or not spawns:
                        continue
                    max_alive = max(0, int(nest_raw.get("max_alive", 12)))
                    burst = max(1, int(nest_raw.get("spawn_burst_size", max_alive or 8)))
                    raw_initial = nest_raw.get("initial_burst_size")
                    initial_burst = (
                        max(0, int(raw_initial))
                        if raw_initial is not None
                        else None
                    )
                    nests.append(
                        WaveNestDef(
                            holes=holes,
                            hole_max_hp=float(nest_raw.get("hole_max_hp", 180.0)),
                            max_alive=max_alive,
                            spawn_interval_ticks=max(
                                0, int(nest_raw.get("spawn_interval_ticks", 20))
                            ),
                            spawn_burst_size=burst,
                            initial_burst_size=initial_burst,
                            spawns=spawns,
                        )
                    )
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
        self._burst_announced = False
        self._holes.clear()
        self._spawner_root_ids.clear()
        self._nest_states.clear()

    def abort_wave(self, world: "World | None" = None) -> None:
        """防衛中断（プレイヤー敗北など）。"""
        if world is not None:
            self._teardown_wave_objects(world)
        self._wave_active = False
        self._all_spawned = True
        self._nests_ready = False
        self._holes.clear()
        self._spawner_root_ids.clear()
        self._nest_states.clear()

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
        self._spawned_ids.clear()
        self._all_spawned = False
        self._nests_ready = False
        self._burst_announced = False
        self._holes.clear()
        self._spawner_root_ids.clear()
        self._nest_states.clear()
        if wave_index < 0 or wave_index >= len(self.waves):
            self._wave_active = False
            self._wave_index = -1
            return []
        self._wave_index = wave_index
        self._wave_active = True
        wave = self.waves[wave_index]
        for nest in wave.nests:
            budgets = {s.species: int(s.budget) for s in nest.spawns if s.budget > 0}
            self._nest_states.append(_NestSpawnState(budgets=budgets))
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

        if not self._nests_ready:
            self._ensure_nests(world)

        self._prune_dead(world)

        if not self._all_spawned:
            burst_msgs = self._tick_spawners(world, bridge)
            messages.extend(burst_msgs)

        if self._all_spawned and self.enemies_alive(world) == 0 and self._all_holes_destroyed(world):
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

    def _ensure_nests(self, world: "World") -> None:
        wave = self.current_wave
        if wave is None:
            self._nests_ready = True
            self._all_spawned = True
            return

        self._teardown_wave_objects(world)
        self._holes.clear()
        self._spawner_root_ids.clear()

        # Per-hole spawner compounds at waves.json coordinates only.
        for nest_idx, nest in enumerate(wave.nests):
            for hole_idx, hole in enumerate(nest.holes):
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
                    max_hp=float(nest.hole_max_hp),
                    shelter=False,
                    deposit_access=False,
                    withdraw_access=False,
                )
                if access is not None:
                    self._holes.append(access.id)

        self._nests_ready = True

    def _teardown_wave_objects(self, world: "World") -> None:
        """Remove wave spawner roots/access (not player/rival faction sites)."""
        cs = world.compound_system
        for hid in list(self._holes):
            cs.remove_access_point(hid)
        self._holes.clear()
        ws = world.world_object_system
        for root_id in list(self._spawner_root_ids):
            for child in list(ws.get_children(root_id)):
                cs.remove_access_point(child.id)
            ws.objects.pop(root_id, None)
            ws._children.pop(root_id, None)
        self._spawner_root_ids.clear()

    def _all_holes_destroyed(self, world: "World") -> bool:
        if not self._holes:
            return True
        ws = world.world_object_system
        for hid in self._holes:
            obj = ws.get(hid)
            if obj is not None and not obj.is_destroyed:
                return False
        return True

    def _prune_dead(self, world: "World") -> None:
        live_ids: set[int] = set()
        for creature in getattr(world, "creatures", ()) or ():
            cid = id(creature)
            if cid in self._spawned_ids and getattr(creature, "alive", True):
                live_ids.add(cid)
        self._spawned_ids = live_ids

    def _tick_spawners(self, world: "World", bridge: "SimBridge") -> list[GameMessage]:
        wave = self.current_wave
        if wave is None:
            self._all_spawned = True
            return []

        # Stop spawning if every hole is gone.
        if self._all_holes_destroyed(world):
            self._all_spawned = True
            return []

        messages: list[GameMessage] = []
        any_remaining_budget = False
        wave_burst_total = 0

        for i, nest in enumerate(wave.nests):
            if i >= len(self._nest_states):
                continue
            state = self._nest_states[i]

            if state.remaining_budget() <= 0:
                continue
            any_remaining_budget = True

            if not state.initial_burst_done:
                target = nest.initial_burst_size
                if target is None:
                    target = nest.max_alive if nest.max_alive > 0 else nest.spawn_burst_size
                limit = min(int(target), state.remaining_budget())
                if nest.max_alive > 0:
                    limit = min(limit, nest.max_alive)
                spawned = self._spawn_batch(world, bridge, nest, state, limit)
                state.initial_burst_done = True
                state.spawn_cooldown = max(0, int(nest.spawn_interval_ticks))
                wave_burst_total += spawned
                continue

            if state.spawn_cooldown > 0:
                state.spawn_cooldown -= 1
                continue

            if nest.max_alive > 0:
                deficit = nest.max_alive - self.enemies_alive(world)
                if deficit <= 0:
                    continue
                limit = min(deficit, nest.spawn_burst_size, state.remaining_budget())
            else:
                limit = min(nest.spawn_burst_size, state.remaining_budget())

            if limit <= 0:
                continue

            self._spawn_batch(world, bridge, nest, state, limit)
            state.spawn_cooldown = max(0, int(nest.spawn_interval_ticks))

        if wave_burst_total > 0 and not self._burst_announced:
            self._burst_announced = True
            messages.append(
                GameMessage(
                    text=f"敵の巣穴から侵入蟻が一気に湧き出した（{wave_burst_total} 匹）",
                    source="phase",
                    priority=4,
                )
            )

        if not any_remaining_budget:
            self._all_spawned = True
        return messages

    def _spawn_batch(
        self,
        world: "World",
        bridge: "SimBridge",
        nest: WaveNestDef,
        state: _NestSpawnState,
        limit: int,
    ) -> int:
        """Spawn up to `limit` enemies from live holes; returns count actually spawned."""
        spawned = 0
        attempts = 0
        max_attempts = max(limit * 3, limit)
        while spawned < limit and attempts < max_attempts:
            attempts += 1
            if nest.max_alive > 0 and self.enemies_alive(world) >= nest.max_alive:
                break
            if state.remaining_budget() <= 0:
                break

            hole_obj = self._pick_live_hole(world, state.spawn_cursor)
            state.spawn_cursor += 1
            if hole_obj is None:
                break

            species = self._pick_next_species(state)
            if species is None:
                break

            creature = self._spawn_enemy_at(
                world, bridge, species, float(hole_obj.x), float(hole_obj.y)
            )
            state.budgets[species] = max(0, int(state.budgets.get(species, 0)) - 1)
            if creature is not None:
                self._spawned_ids.add(id(creature))
                spawned += 1
        return spawned

    def _pick_live_hole(self, world: "World", cursor: int) -> Any | None:
        if not self._holes:
            return None
        ws = world.world_object_system
        n = len(self._holes)
        for k in range(n):
            hid = self._holes[(cursor + k) % n]
            obj = ws.get(hid)
            if obj is None:
                continue
            if obj.is_destroyed:
                continue
            return obj
        return None

    def _pick_next_species(self, state: _NestSpawnState) -> str | None:
        for species, budget in list(state.budgets.items()):
            if int(budget) > 0:
                return str(species)
        return None

    def _spawn_enemy_at(
        self,
        world: "World",
        bridge: "SimBridge",
        species: str,
        x: float,
        y: float,
    ) -> Any | None:
        from src.game.command_builder import spawn_creature as bridge_spawn

        creature = bridge_spawn(bridge, species, x=x, y=y, source="game")
        if creature is not None:
            from src.game.command_builder import apply_spawn_profile

            apply_spawn_profile(bridge, creature)
        return creature

    # ---- test helpers (non-gameplay) -------------------------------------------------

    def debug_exhaust_budgets(self) -> None:
        """Force spawners to stop (for unit tests)."""
        for st in self._nest_states:
            for k in list(st.budgets.keys()):
                st.budgets[k] = 0
        self._all_spawned = True

    def debug_destroy_all_holes(self, world: "World") -> None:
        """Force all wave holes to be destroyed/removed (for unit tests)."""
        self._teardown_wave_objects(world)
