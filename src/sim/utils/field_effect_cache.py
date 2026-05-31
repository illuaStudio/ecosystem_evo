"""セル単位の環境フィールド modifier キャッシュ（バイオーム・ゾーン・テリトリー）。"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from src.sim.utils.creature_helpers import is_point_in_colony_territory
from src.sim.utils.field_modifiers import FieldModifiers, get_field_immunities
from src.sim.utils.position_helpers import entity_xy

if TYPE_CHECKING:
    from src.sim.systems.world import World
    from src.sim.systems.zone_system import ZoneSample


class FieldEffectCache:
    """座標セルごとの環境 HP modifier を事前計算し、毎 tick のノイズ評価を避ける。"""

    def __init__(self, world: "World") -> None:
        self._world = world
        self._dirty = True
        self._cell_size = 16
        self._cols = 0
        self._rows = 0
        self._biome: list[list[FieldModifiers]] = []
        self._zone: list[list["ZoneSample"]] = []
        self._territory_colony_ids: tuple[str, ...] = ()
        self._territory_active: dict[str, list[list[bool]]] = {}
        self._territory_modifiers = FieldModifiers()

    def mark_dirty(self) -> None:
        self._dirty = True

    def rebuild(self) -> None:
        self._build()
        self._dirty = False

    def ensure_built(self) -> None:
        if self._dirty:
            self.rebuild()

    def _cell_size_for_world(self) -> int:
        biome = getattr(self._world, "biome", None)
        if biome is not None:
            return max(4, int(getattr(biome, "biome_cell_size", 16)))
        return 16

    def _pos_to_cell(self, x: float, y: float) -> tuple[int, int]:
        cell = self._cell_size
        col = int(x // cell)
        row = int(y // cell)
        col = max(0, min(self._cols - 1, col))
        row = max(0, min(self._rows - 1, row))
        return col, row

    def _colony_ids_for_territory(self) -> tuple[str, ...]:
        world = self._world
        ids: set[str] = set()
        for cid in (getattr(world, "faction_species", {}) or {}):
            if cid:
                ids.add(str(cid))
        from src.sim.utils.world_object_helpers import iter_active_colony_roots

        for root in iter_active_colony_roots(world):
            if root.id:
                ids.add(str(root.id))
        return tuple(sorted(ids))

    def _resolve_territory_modifiers(self) -> FieldModifiers:
        colony_settings = getattr(self._world, "colony_settings", None) or {}
        effects = colony_settings.get("territory_effects") or {}
        if not effects:
            return FieldModifiers()
        regen = float(effects.get("hp_regen_per_dt", 0.0))
        drain = float(effects.get("hp_drain_per_dt", 0.0))
        if regen == 0.0 and drain == 0.0:
            return FieldModifiers()
        if bool(effects.get("requires_colony_match", True)):
            return FieldModifiers(hp_regen_per_dt=regen, hp_drain_per_dt=drain)
        return FieldModifiers(hp_regen_per_dt=regen, hp_drain_per_dt=drain)

    def _build(self) -> None:
        world = self._world
        cell = self._cell_size_for_world()
        self._cell_size = cell
        self._cols = max(1, math.ceil(world.width / cell))
        self._rows = max(1, math.ceil(world.height / cell))

        biome_rows: list[list[FieldModifiers]] = []
        zone_rows: list[list[Any]] = []
        zone_system = getattr(world, "zone_system", None)

        for row in range(self._rows):
            cy = row * cell + cell * 0.5
            biome_row: list[FieldModifiers] = []
            zone_row: list[Any] = []
            for col in range(self._cols):
                cx = col * cell + cell * 0.5
                biome = world.biome.get_biome_at(cx, cy)
                biome_row.append(
                    FieldModifiers(
                        hp_regen_per_dt=float(biome.get("hp_regen_per_dt", 0.0)),
                        hp_drain_per_dt=float(biome.get("hp_drain_per_dt", 0.0)),
                    )
                )
                if zone_system is not None:
                    zone_row.append(zone_system.sample_at(cx, cy))
                else:
                    from src.sim.systems.zone_system import ZoneSample

                    zone_row.append(ZoneSample())
            biome_rows.append(biome_row)
            zone_rows.append(zone_row)

        self._biome = biome_rows
        self._zone = zone_rows

        self._territory_modifiers = self._resolve_territory_modifiers()
        colony_settings = getattr(world, "colony_settings", None) or {}
        effects = colony_settings.get("territory_effects") or {}
        requires_match = bool(effects.get("requires_colony_match", True))
        colony_ids = self._colony_ids_for_territory()
        self._territory_colony_ids = colony_ids

        territory_active: dict[str, list[list[bool]]] = {}
        if self._territory_modifiers != FieldModifiers() and requires_match:
            for colony_id in colony_ids:
                rows: list[list[bool]] = []
                for row in range(self._rows):
                    cy = row * cell + cell * 0.5
                    row_flags: list[bool] = []
                    for col in range(self._cols):
                        cx = col * cell + cell * 0.5
                        row_flags.append(
                            is_point_in_colony_territory(world, colony_id, cx, cy)
                        )
                    rows.append(row_flags)
                territory_active[colony_id] = rows
        self._territory_active = territory_active

    def _territory_for_creature(self, creature: Any, col: int, row: int) -> FieldModifiers:
        if self._territory_modifiers == FieldModifiers():
            return FieldModifiers()

        colony_settings = getattr(self._world, "colony_settings", None) or {}
        effects = colony_settings.get("territory_effects") or {}
        requires_match = bool(effects.get("requires_colony_match", True))

        if not requires_match:
            return self._territory_modifiers

        from src.sim.utils.colony_helpers import get_creature_colony_id

        colony_id = get_creature_colony_id(creature)
        if not colony_id:
            return FieldModifiers()

        grid = self._territory_active.get(str(colony_id))
        if grid is None or not grid[row][col]:
            return FieldModifiers()
        return self._territory_modifiers

    def _zone_for_creature(self, creature: Any, col: int, row: int) -> FieldModifiers:
        sample = self._zone[row][col]
        if (
            sample.hp_regen_per_dt <= 0
            and sample.hp_drain_per_dt <= 0
            and not sample.field_tags
        ):
            return FieldModifiers()

        immune = get_field_immunities(creature)
        if immune.intersection(sample.field_tags):
            return FieldModifiers(hp_regen_per_dt=sample.hp_regen_per_dt)

        return FieldModifiers(
            hp_regen_per_dt=sample.hp_regen_per_dt,
            hp_drain_per_dt=sample.hp_drain_per_dt,
        )

    def sample_for_creature(self, creature: Any) -> FieldModifiers:
        """個体位置のセルから modifier を合成（キャッシュ参照）。"""
        self.ensure_built()
        x, y = entity_xy(creature)
        col, row = self._pos_to_cell(x, y)
        biome = self._biome[row][col]
        territory = self._territory_for_creature(creature, col, row)
        zone = self._zone_for_creature(creature, col, row)
        return biome.merged_with(territory).merged_with(zone)


def invalidate_field_effect_cache(world: Any) -> None:
    cache = getattr(world, "field_effect_cache", None)
    if cache is not None:
        cache.mark_dirty()
