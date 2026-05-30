"""環境発生源（毒霧など）の描画。"""
import pygame

from src.systems.field_emitter_system import FieldEmitter


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


class FieldEmitterRenderer:
    @staticmethod
    def _style_for(emitter: FieldEmitter) -> dict:
        if emitter.emitter_type == "poison_fog":
            return POISON_FOG_STYLE
        return POISON_FOG_STYLE

    @staticmethod
    def _draw_zone(
        screen,
        camera,
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
    def draw(world, screen, camera) -> None:
        system = getattr(world, "field_emitter_system", None)
        if system is None:
            return

        for emitter in system.emitters:
            sx = int(emitter.x - camera.x)
            sy = int(emitter.y - camera.y)
            radius = int(emitter.radius)
            if not (
                -radius - 20 <= sx <= camera.screen_w + radius + 20
                and -radius - 20 <= sy <= camera.screen_h + radius + 20
            ):
                continue

            style = FieldEmitterRenderer._style_for(emitter)
            FieldEmitterRenderer._draw_zone(
                screen,
                camera,
                sx,
                sy,
                radius,
                _rgba(style.get("zone_fill"), POISON_FOG_STYLE["zone_fill"]),
                _rgba(style.get("zone_line"), POISON_FOG_STYLE["zone_line"]),
            )

            outer = _rgba(style.get("core_outer"), (*POISON_FOG_STYLE["core_outer"], 255))[:3]
            inner = _rgba(style.get("core_inner"), (*POISON_FOG_STYLE["core_inner"], 255))[:3]
            pygame.draw.circle(screen, outer, (sx, sy), 10, 2)
            pygame.draw.circle(screen, inner, (sx, sy), 6)
            pygame.draw.circle(screen, (210, 255, 190), (sx, sy), 2)
