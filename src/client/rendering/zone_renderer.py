"""Zone（毒霧・巣周辺クリアリングなど）の描画。"""
import pygame

from src.sim.systems.zone_system import Zone


def _clamp_channel(value) -> int:
    return max(0, min(255, int(value)))


def _rgba(raw, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        alpha = _clamp_channel(raw[3]) if len(raw) >= 4 else default[3]
        return (
            _clamp_channel(raw[0]),
            _clamp_channel(raw[1]),
            _clamp_channel(raw[2]),
            alpha,
        )
    return default


POISON_FOG_STYLE = {
    "zone_fill": (80, 180, 70, 42),
    "zone_line": (120, 230, 100, 110),
    "core_outer": (40, 90, 35),
    "core_inner": (150, 240, 120),
}

NEST_CLEARING_STYLE = {
    "zone_fill": (180, 180, 180, 22),
    "zone_line": (200, 200, 200, 55),
}


class ZoneRenderer:
    @staticmethod
    def _style_for(zone: Zone) -> dict | None:
        effects = zone.effects
        if effects.spawn_rate_multiplier is not None and effects.spawn_rate_multiplier <= 0:
            return NEST_CLEARING_STYLE
        if effects.hp_drain_per_dt > 0 or "poison" in effects.field_tags:
            return POISON_FOG_STYLE
        if effects.hp_regen_per_dt > 0:
            return {
                "zone_fill": (70, 130, 220, 30),
                "zone_line": (100, 170, 255, 80),
            }
        return None

    @staticmethod
    def _draw_circle_zone(
        screen,
        sx: int,
        sy: int,
        radius: int,
        fill_rgba: tuple[int, int, int, int],
        line_rgba: tuple[int, int, int, int],
    ) -> None:
        pad = radius + 8
        size = pad * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (pad, pad)
        pygame.draw.circle(surf, fill_rgba, center, radius)
        pygame.draw.circle(surf, line_rgba, center, radius, 2)
        screen.blit(surf, (sx - pad, sy - pad))

    @staticmethod
    def _draw_rect_zone(
        screen,
        sx: int,
        sy: int,
        half_w: int,
        half_h: int,
        fill_rgba: tuple[int, int, int, int],
        line_rgba: tuple[int, int, int, int],
    ) -> None:
        pad = 8
        w = half_w * 2 + pad * 2
        h = half_h * 2 + pad * 2
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        rect = pygame.Rect(pad, pad, half_w * 2, half_h * 2)
        pygame.draw.rect(surf, fill_rgba, rect)
        pygame.draw.rect(surf, line_rgba, rect, 2)
        screen.blit(surf, (sx - half_w - pad, sy - half_h - pad))

    @staticmethod
    def draw(world, screen, camera) -> None:
        system = getattr(world, "zone_system", None)
        if system is None:
            return

        for zone in system.zones:
            style = ZoneRenderer._style_for(zone)
            if style is None:
                continue

            sx = int(zone.x - camera.x)
            sy = int(zone.y - camera.y)
            fill = _rgba(style.get("zone_fill"), POISON_FOG_STYLE["zone_fill"])
            line = _rgba(style.get("zone_line"), POISON_FOG_STYLE["zone_line"])

            if zone.is_rect:
                half_w = int(zone.half_w)
                half_h = int(zone.half_h)
                if not (
                    -half_w - 20 <= sx <= camera.screen_w + half_w + 20
                    and -half_h - 20 <= sy <= camera.screen_h + half_h + 20
                ):
                    continue
                ZoneRenderer._draw_rect_zone(screen, sx, sy, half_w, half_h, fill, line)
            else:
                radius = int(zone.radius)
                if not (
                    -radius - 20 <= sx <= camera.screen_w + radius + 20
                    and -radius - 20 <= sy <= camera.screen_h + radius + 20
                ):
                    continue
                ZoneRenderer._draw_circle_zone(screen, sx, sy, radius, fill, line)

            if zone.effects.hp_drain_per_dt > 0:
                outer = _rgba(style.get("core_outer"), (*POISON_FOG_STYLE["core_outer"], 255))[:3]
                inner = _rgba(style.get("core_inner"), (*POISON_FOG_STYLE["core_inner"], 255))[:3]
                pygame.draw.circle(screen, outer, (sx, sy), 10, 2)
                pygame.draw.circle(screen, inner, (sx, sy), 6)
                pygame.draw.circle(screen, (210, 255, 190), (sx, sy), 2)
