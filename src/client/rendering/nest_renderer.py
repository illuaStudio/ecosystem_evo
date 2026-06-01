# nest_renderer.py
import pygame

from src.game.colony_session import try_get_colony_orchestrator
from src.sim.utils.territory_helpers import get_territory_radius_for_affiliation, iter_territory_centers

DEFAULT_FACTION_STYLE = {
    "label": "?",
    "territory_fill": (120, 180, 120, 34),
    "territory_line": (160, 220, 160, 130),
    "nest_outer": (80, 80, 80),
    "nest_inner_base": (140, 140, 140),
    "nest_glow_base": (60, 100, 60),
    "affiliation_access": (220, 220, 200),
}


def get_faction_style(world, affiliation_id: str) -> dict:
    """ワールド JSON の colony.factions から勢力の見た目を取得。"""
    styles = getattr(world, "affiliation_styles", None) or {}
    raw = styles.get(affiliation_id)
    if not raw:
        return dict(DEFAULT_FACTION_STYLE)
    out = dict(DEFAULT_FACTION_STYLE)
    out.update(raw)
    return out


def _clamp_channel(value) -> int:
    return max(0, min(255, int(value)))


def _rgb_tuple(raw, default: tuple) -> tuple:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return (
            _clamp_channel(raw[0]),
            _clamp_channel(raw[1]),
            _clamp_channel(raw[2]),
        )
    return default[:3]


def _rgba_tuple(raw, default: tuple) -> tuple:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        if len(raw) >= 4:
            return (
                _clamp_channel(raw[0]),
                _clamp_channel(raw[1]),
                _clamp_channel(raw[2]),
                _clamp_channel(raw[3]),
            )
        return (
            _clamp_channel(raw[0]),
            _clamp_channel(raw[1]),
            _clamp_channel(raw[2]),
            default[3],
        )
    return default


class NestRenderer:
    @staticmethod
    def _hole_hp_bar_color(ratio: float) -> tuple[int, int, int]:
        ratio = max(0.0, min(1.0, ratio))
        if ratio > 0.55:
            return (90, 220, 110)
        if ratio > 0.25:
            return (240, 200, 60)
        return (240, 90, 70)

    @staticmethod
    def _faction_colony_access_color(faction: dict) -> tuple:
        raw = faction.get("affiliation_access")
        if raw is None:
            raw = faction.get("nest_hole")
        return _rgb_tuple(raw, DEFAULT_FACTION_STYLE["affiliation_access"])

    @staticmethod
    def _draw_access_hp(screen, hx: int, hy: int, hp: float, max_hp: float) -> None:
        """colony_access の体力バーと数値（常時表示）。"""
        if max_hp <= 0:
            return
        ratio = max(0.0, min(1.0, hp / max_hp))
        bar_w = 18
        bar_h = 4
        bar_x = hx - bar_w // 2
        bar_y = hy - 16
        pygame.draw.rect(screen, (30, 30, 30), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
        fill_w = max(0, int(bar_w * ratio))
        if fill_w > 0:
            pygame.draw.rect(
                screen,
                NestRenderer._hole_hp_bar_color(ratio),
                (bar_x, bar_y, fill_w, bar_h),
            )
        font = pygame.font.SysFont("msgothic", 9)
        if 0 < hp < 1.0:
            hp_text = f"{hp:.1f}"
        else:
            hp_text = str(max(0, int(round(hp))))
        label = font.render(f"{hp_text}/{int(max_hp)}", True, (235, 235, 220))
        screen.blit(label, (hx - label.get_width() // 2, bar_y - 11))

    @staticmethod
    def _draw_territory_circle(
        screen,
        camera,
        cx: float,
        cy: float,
        territory_r: int,
        fill_rgba: tuple,
        line_rgba: tuple,
        *,
        emphasize: bool = False,
    ) -> None:
        sx = int(cx - camera.x)
        sy = int(cy - camera.y)
        pad = territory_r + 8
        if not (
            -pad <= sx <= camera.screen_w + pad
            and -pad <= sy <= camera.screen_h + pad
        ):
            return

        if emphasize:
            fill_rgba = (
                min(255, fill_rgba[0] + 30),
                min(255, fill_rgba[1] + 20),
                min(255, fill_rgba[2] + 10),
                min(255, fill_rgba[3] + 24),
            )
            line_rgba = (
                min(255, line_rgba[0] + 20),
                min(255, line_rgba[1] + 30),
                min(255, line_rgba[2] + 20),
                220,
            )

        diameter = territory_r * 2 + 4
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        center = (territory_r + 2, territory_r + 2)
        pygame.draw.circle(surf, fill_rgba, center, territory_r)
        pygame.draw.circle(surf, line_rgba, center, territory_r, 2)
        if emphasize:
            pygame.draw.circle(surf, line_rgba, center, territory_r + 3, 1)
        screen.blit(surf, (sx - territory_r - 2, sy - territory_r - 2))

    @staticmethod
    def draw_territories(
        world,
        screen,
        camera,
        *,
        show_territory: bool = False,
        selected_affiliation_id: str | None = None,
    ) -> None:
        """全コロニーのテリトリーを colony_access ごとの円で描画（T キー切替）。"""
        if not show_territory:
            return

        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        for root in iter_active_affiliation_roots(world):
            affiliation_id = root.id
            territory_r = int(get_territory_radius_for_affiliation(world, affiliation_id))
            if territory_r <= 0:
                continue

            faction = get_faction_style(world, affiliation_id)
            fill_rgba = _rgba_tuple(
                faction.get("territory_fill"), DEFAULT_FACTION_STYLE["territory_fill"]
            )
            line_rgba = _rgba_tuple(
                faction.get("territory_line"), DEFAULT_FACTION_STYLE["territory_line"]
            )
            selected = selected_affiliation_id is not None and affiliation_id == selected_affiliation_id

            for cx, cy in iter_territory_centers(affiliation_id, world):
                NestRenderer._draw_territory_circle(
                    screen,
                    camera,
                    cx,
                    cy,
                    territory_r,
                    fill_rgba,
                    line_rgba,
                    emphasize=selected,
                )

    @staticmethod
    def draw_affiliation_access_placement_preview(
        world,
        screen,
        camera,
        affiliation_id: str,
        wx: float,
        wy: float,
    ) -> None:
        """選択中のコロニーへの colony_access 設置可否をカーソル位置に表示。"""
        if not affiliation_id:
            return
        ns = try_get_colony_orchestrator(world)
        if ns is None:
            return

        ok, _ = ns.can_place_hole(affiliation_id, wx, wy)
        sx = int(wx - camera.x)
        sy = int(wy - camera.y)
        color = (100, 220, 140) if ok else (240, 90, 90)
        pygame.draw.circle(screen, color, (sx, sy), 10, 2)
        pygame.draw.circle(screen, (*color[:3], 60), (sx, sy), 6)

    @staticmethod
    def draw(world, screen, camera, selected_affiliation_id: str | None = None) -> None:
        from src.sim.utils.world_object_helpers import (
            affiliation_fill_ratio,
            affiliation_site_xy,
            iter_active_affiliation_roots,
            iter_affiliation_access_for_display,
            owner_species_for_affiliation,
        )

        nest_system = try_get_colony_orchestrator(world)
        if nest_system is None:
            return

        for root in iter_active_affiliation_roots(world):
            affiliation_id = root.id
            site_x, site_y = affiliation_site_xy(world, affiliation_id)
            sx = int(site_x - camera.x)
            sy = int(site_y - camera.y)
            if not (
                -80 <= sx <= camera.screen_w + 80
                and -80 <= sy <= camera.screen_h + 80
            ):
                continue

            fill = affiliation_fill_ratio(world, affiliation_id)
            faction = get_faction_style(world, affiliation_id)
            outer = _rgb_tuple(faction.get("nest_outer"), DEFAULT_FACTION_STYLE["nest_outer"])
            ib = _rgb_tuple(
                faction.get("nest_inner_base"),
                DEFAULT_FACTION_STYLE["nest_inner_base"],
            )
            inner = (
                _clamp_channel(ib[0] + fill * 60),
                _clamp_channel(ib[1] + fill * 100),
                _clamp_channel(ib[2] + fill * 30),
            )
            radius = 14 + int(fill * 10)
            selected = selected_affiliation_id is not None and affiliation_id == selected_affiliation_id
            if selected:
                pygame.draw.circle(screen, (255, 240, 120), (sx, sy), radius + 10, 2)
            pygame.draw.circle(screen, outer, (sx, sy), radius + 4, 2)
            pygame.draw.circle(screen, inner, (sx, sy), radius)
            center_dot = (
                _clamp_channel(ib[0] + 75),
                _clamp_channel(ib[1] + 110),
                _clamp_channel(ib[2] + 80),
            )
            pygame.draw.circle(screen, center_dot, (sx, sy), 5)

            access_fill = NestRenderer._faction_colony_access_color(faction)
            for access in iter_affiliation_access_for_display(world, affiliation_id):
                hx = int(float(access.x) - camera.x)
                hy = int(float(access.y) - camera.y)
                max_hp = float(getattr(access, "max_hp", 0) or 1)
                hp = float(getattr(access, "hp", max_hp))
                pygame.draw.circle(screen, access_fill, (hx, hy), 4)
                pygame.draw.circle(screen, outer, (hx, hy), 6, 1)
                NestRenderer._draw_access_hp(screen, hx, hy, hp, max_hp)

            if fill > 0.05:
                gb = _rgb_tuple(
                    faction.get("nest_glow_base"),
                    DEFAULT_FACTION_STYLE["nest_glow_base"],
                )
                leak_glow = (
                    _clamp_channel(gb[0] + fill * 40),
                    _clamp_channel(gb[1] + fill * 80),
                    _clamp_channel(gb[2] + fill * 50),
                )
                pygame.draw.circle(
                    screen, leak_glow, (sx, sy), radius + 8, 1
                )

            members = nest_system.total_member_count(affiliation_id)
            font = pygame.font.SysFont("msgothic", 11)
            owner_tag = faction.get("label")
            if owner_tag:
                tag_surf = font.render(str(owner_tag), True, (255, 245, 220))
                screen.blit(tag_surf, (sx - 4, sy + radius + 2))
            if members > 0:
                label = font.render(str(members), True, (255, 230, 200))
                screen.blit(label, (sx - 4, sy - radius - 16))
            if fill > 0.08:
                food_pct = int(fill * 100)
                food_label = font.render(f"食{food_pct}", True, (255, 210, 140))
                screen.blit(food_label, (sx - 10, sy + radius + 4))

        NestRenderer._draw_inactive_colony_sites(world, screen, camera)

    @staticmethod
    def _draw_inactive_colony_sites(world, screen, camera) -> None:
        """敗北などで非アクティブな colony_site を薄く表示。"""
        ws = getattr(world, "world_object_system", None)
        if ws is None:
            return
        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        active = {root.id for root in iter_active_affiliation_roots(world)}
        from src.game.colony_session import get_defeated_affiliations

        defeated = get_defeated_affiliations(world)

        for root in ws.iter_roots():
            if root.id in active or root.id in defeated:
                continue
            sx = int(root.x - camera.x)
            sy = int(root.y - camera.y)
            if not (
                -80 <= sx <= camera.screen_w + 80
                and -80 <= sy <= camera.screen_h + 80
            ):
                continue
            faction = get_faction_style(world, root.id)
            outer = _rgb_tuple(faction.get("nest_outer"), DEFAULT_FACTION_STYLE["nest_outer"])
            dim = tuple(max(0, c // 2) for c in outer)
            pygame.draw.circle(screen, dim, (sx, sy), 12, 2)
            for child in ws.iter_access_points(root.id):
                hx = int(child.x - camera.x)
                hy = int(child.y - camera.y)
                pygame.draw.circle(screen, dim, (hx, hy), 3, 1)
            label = faction.get("label", root.id[:1])
            font = pygame.font.SysFont("msgothic", 10)
            tag = font.render(str(label), True, (180, 170, 150))
            screen.blit(tag, (sx - 4, sy + 10))
