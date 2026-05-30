"""種族・生態グループの表示 ON/OFF（シミュレーションは継続、描画・選択のみ制御）。"""
from __future__ import annotations

from dataclasses import dataclass

from src.config import config

# (group_id, 表示名, 種名タプル)
DEFAULT_VISIBILITY_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("amoeba", "アメーバ", ("Amoeba",)),
    ("red_ant", "赤アリ", ("red_ant", "red_ant_soldier", "red_ant_vanguard")),
    ("blue_ant", "青アリ", ("blue_ant", "blue_ant_soldier", "blue_ant_vanguard")),
    ("yellow_ant", "黄アリ", ("yellow_ant", "yellow_ant_soldier", "yellow_ant_vanguard")),
    ("spider", "クモ", ("Spider",)),
)

GROUP_HOTKEYS: dict[int, str] = {
    ord("1"): "amoeba",
    ord("2"): "red_ant",
    ord("3"): "blue_ant",
    ord("4"): "yellow_ant",
    ord("5"): "spider",
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
            for name in names:
                if name in self._visible:
                    self._visible[name] = new_val
            return

    def toggle_group_by_hotkey(self, key: int) -> bool:
        group_id = GROUP_HOTKEYS.get(key)
        if group_id is None:
            return False
        self.toggle_group(group_id)
        return True

    def groups_for_world(self, world) -> list[tuple[str, str, tuple[str, ...]]]:
        limits = getattr(world, "population_limits", None) or {}
        if not limits:
            return list(self._groups)
        out: list[tuple[str, str, tuple[str, ...]]] = []
        for gid, label, names in self._groups:
            filtered = tuple(n for n in names if n in limits)
            if filtered:
                out.append((gid, label, filtered))
        return out

    def set_toggle_rects(self, rects: list[VisibilityToggleRect]) -> None:
        self._toggle_rects = list(rects)

    def hit_test_toggle(self, mx: int, my: int) -> str | None:
        for entry in self._toggle_rects:
            x, y, w, h = entry.rect
            if x <= mx < x + w and y <= my < y + h:
                return entry.group_id
        return None

    def representative_color(self, group_id: str) -> tuple[int, int, int]:
        for gid, _label, names in self._groups:
            if gid != group_id:
                continue
            for name in names:
                data = config.get_species(name) or {}
                color = data.get("color")
                if color and len(color) >= 3:
                    return (int(color[0]), int(color[1]), int(color[2]))
        return (180, 180, 180)
