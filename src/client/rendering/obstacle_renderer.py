"""障害物（石・倒木など）の描画。"""
import pygame

from src.sim.systems.obstacle_system import ObstacleCircle, ObstacleRect


class ObstacleRenderer:
    @staticmethod
    def draw(world, screen, camera) -> None:
        system = getattr(world, "obstacle_system", None)
        if system is None or not system.obstacles:
            return

        pad = 4
        for obs in system.obstacles:
            sx = int(obs.x - camera.x)
            sy = int(obs.y - camera.y)

            if isinstance(obs, ObstacleCircle):
                radius = int(obs.radius)
                if not (
                    -radius - pad <= sx <= camera.screen_w + radius + pad
                    and -radius - pad <= sy <= camera.screen_h + radius + pad
                ):
                    continue
                fill = obs.color
                outline = tuple(max(0, c - 35) for c in fill)
                pygame.draw.circle(screen, fill, (sx, sy), radius)
                pygame.draw.circle(screen, outline, (sx, sy), radius, 2)
                continue

            hw = int(obs.half_w)
            hh = int(obs.half_h)
            if not (
                -hw - pad <= sx <= camera.screen_w + hw + pad
                and -hh - pad <= sy <= camera.screen_h + hh + pad
            ):
                continue
            rect = pygame.Rect(sx - hw, sy - hh, hw * 2, hh * 2)
            fill = obs.color
            outline = tuple(max(0, c - 35) for c in fill)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, outline, rect, 2)
