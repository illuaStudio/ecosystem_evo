"""種族・生態グループの表示 ON/OFF（シミュレーションは継続、描画・選択のみ制御）。"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import config

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES

# (group_id, 表示名, 種名タプル)
DEFAULT_VISIBILITY_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("micro_fauna", "極小虫", DEFAULT_MICRO_FAUNA_SPECIES),
    ("red_ant", "赤アリ", ("red_ant", "red_ant_soldier", "red_ant_vanguard", "red_ant_queen")),
    ("spider", "クモ", ("Spider",)),
)

GROUP_HOTKEYS: dict[int, str] = {
    ord("1"): "micro_fauna",
    ord("2"): "red_ant",
    ord("3"): "spider",
}


@dataclass(frozen=True)
class VisibilityToggleRect:
    group_id: str
    rect: tuple[int, int, int, int]  # x, y, w, h


class SpeciesVisibilityManager:
    """種名単位の表示フラグ。UI は生態グループでまとめて切り替え。"""

    def __init__(self) -> None:
        self._visible: dict[str, bool] = {}
        self._groups = list(DEFAULT_VISIBILITY_GROUPS)
        self._toggle_rects: list[VisibilityToggleRect] = []

    def reset_for_world(self, world) -> None:
        """ワールドの population_limits に合わせてフラグを初期化（未登録は表示 ON）。"""
        limits = getattr(world, "population_limits", None) or {}
        for name in limits:
            self._visible[name] = True
        for _gid, _label, species_names in self._groups:
            for name in species_names:
                if name in limits:
                    self._visible.setdefault(name, True)

    def groups_for_world(self, world) -> list[tuple[str, str, tuple[str, ...]]]:
        """population_limits に含まれる種が1つでもある生態グループのみ返す。"""
        limits = getattr(world, "population_limits", None) or {}
        if not limits:
            return list(self._groups)
        return [
            (gid, label, names)
            for gid, label, names in self._groups
            if any(name in limits for name in names)
        ]

    def is_species_visible(self, species_name: str) -> bool:
        return self._visible.get(species_name, True)

    def is_creature_visible(self, creature) -> bool:
        if creature is None:
            return False
        return self.is_species_visible(creature.species.name)

    def group_for_species(self, species_name: str) -> str | None:
        for gid, _label, names in self._groups:
            if species_name in names:
                return gid
        return None

    def is_group_visible(self, group_id: str) -> bool:
        for gid, _label, names in self._groups:
            if gid == group_id:
                if not names:
                    return True
                return any(self.is_species_visible(n) for n in names)
        return True

    def toggle_group(self, group_id: str) -> None:
        for gid, _label, names in self._groups:
            if gid != group_id:
                continue
            if not names:
                return
            new_val = not self.is_group_visible(group_id)
            for n in names:
                self._visible[n] = new_val
            return

    def toggle_group_by_hotkey(self, key: int) -> bool:
        group_id = GROUP_HOTKEYS.get(key)
        if group_id is None:
            return False
        self.toggle_group(group_id)
        return True

    def representative_color(self, group_id: str) -> tuple[int, int, int]:
        for gid, _label, names in self._groups:
            if gid != group_id or not names:
                continue
            for name in names:
                data = config.species.get(name)
                if data and "color" in data:
                    c = data["color"]
                    return int(c[0]), int(c[1]), int(c[2])
        return 180, 180, 180

    @property
    def groups(self) -> list[tuple[str, str, tuple[str, ...]]]:
        return list(self._groups)

    @property
    def toggle_rects(self) -> list[VisibilityToggleRect]:
        return self._toggle_rects

    @toggle_rects.setter
    def toggle_rects(self, rects: list[VisibilityToggleRect]) -> None:
        self._toggle_rects = rects

    def set_toggle_rects(self, rects: list[VisibilityToggleRect]) -> None:
        self._toggle_rects = rects

    def hit_test_toggle(self, x: int, y: int) -> str | None:
        """表示パネルの行クリック判定。該当 group_id または None。"""
        for entry in self._toggle_rects:
            rx, ry, rw, rh = entry.rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return entry.group_id
        return None
