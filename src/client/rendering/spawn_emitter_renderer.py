"""スポーン発生源エリアの描画（デバッグ・探索用）。"""
import pygame

from src.sim.systems.spawn_system import SpawnEmitter


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


MICRO_FAUNA_PATCH_STYLE = {
    "zone_fill": (200, 170, 80, 28),
    "zone_line": (240, 210, 120, 90),
    "core_outer": (180, 140, 60),
    "core_inner": (255, 230, 150),
}


class SpawnEmitterRenderer:
    @staticmethod
    def _draw_zone(
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
        pygame.draw.circle(surf, line_rgba, center, radius, 1)
        screen.blit(surf, (sx - pad, sy - pad))

    @staticmethod
    def draw(world, screen, camera) -> None:
        system = getattr(world, "spawn_system", None)
        if system is None:
            return

        style = MICRO_FAUNA_PATCH_STYLE
        fill = _rgba(style["zone_fill"], MICRO_FAUNA_PATCH_STYLE["zone_fill"])
        line = _rgba(style["zone_line"], MICRO_FAUNA_PATCH_STYLE["zone_line"])
        outer = _rgba(style["core_outer"], (*MICRO_FAUNA_PATCH_STYLE["core_outer"], 255))[:3]
        inner = _rgba(style["core_inner"], (*MICRO_FAUNA_PATCH_STYLE["core_inner"], 255))[:3]

        for emitter in system.emitters:
            if emitter.is_ambient:
                continue
            SpawnEmitterRenderer._draw_emitter(
                screen, camera, emitter, fill, line, outer, inner
            )

    @staticmethod
    def _draw_emitter(screen, camera, emitter: SpawnEmitter, fill, line, outer, inner) -> None:
        sx = int(emitter.x - camera.x)
        sy = int(emitter.y - camera.y)
        radius = int(emitter.radius)
        if not (
            -radius - 20 <= sx <= camera.screen_w + radius + 20
            and -radius - 20 <= sy <= camera.screen_h + radius + 20
        ):
            return

        SpawnEmitterRenderer._draw_zone(screen, sx, sy, radius, fill, line)
        pygame.draw.circle(screen, outer, (sx, sy), 7, 1)
        pygame.draw.circle(screen, inner, (sx, sy), 4)
