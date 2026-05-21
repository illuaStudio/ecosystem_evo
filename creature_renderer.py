# creature_renderer.py
import pygame

from creature_helpers import hp_ratio, satiety_ratio


class CreatureRenderer:
    """生物描画クラス（見えやすく強化）"""

    @staticmethod
    def draw(creature, screen, camera):
        sx = int(creature.pos[0] - camera.x)
        sy = int(creature.pos[1] - camera.y)

        if not (0 - 50 <= sx <= camera.screen_w + 50 and 0 - 50 <= sy <= camera.screen_h + 50):
            return

        color = creature.species.color
        size = int(creature.traits.get("base_size", 8))
        is_carcass = not creature.alive

        if is_carcass:
            color = tuple(max(0, c // 2) for c in color)

        if hasattr(creature, "last_pos"):
            lx = int(creature.last_pos[0] - camera.x)
            ly = int(creature.last_pos[1] - camera.y)
            if abs(lx - sx) + abs(ly - sy) > 2:
                trail_color = (max(0, color[0] - 80), max(0, color[1] - 80), max(0, color[2] - 80))
                pygame.draw.line(screen, trail_color, (lx, ly), (sx, sy), max(2, size // 2))

        pygame.draw.circle(screen, color, (sx, sy), size + 2)
        pygame.draw.circle(screen, (255, 255, 255), (sx, sy), size + 2, 2)

        bar_w = int(size * 3.0)
        bar_x = sx - bar_w // 2

        if is_carcass:
            fill = 0.0 if creature.max_hp <= 0 else creature.carcass_units / creature.max_hp
            bar_y = sy - size - 18
            pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, 6))
            pygame.draw.rect(screen, (160, 120, 80), (bar_x, bar_y, int(bar_w * fill), 6))
        else:
            bar_y_sat = sy - size - 24
            bar_y_hp = sy - size - 14
            sat_fill = satiety_ratio(creature)
            hp_fill = hp_ratio(creature)

            pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y_sat, bar_w, 6))
            pygame.draw.rect(
                screen,
                (80 + int(sat_fill * 175), 255, 80),
                (bar_x, bar_y_sat, int(bar_w * sat_fill), 6),
            )
            pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y_hp, bar_w, 6))
            pygame.draw.rect(
                screen,
                (255, 80 + int(hp_fill * 100), 80),
                (bar_x, bar_y_hp, int(bar_w * hp_fill), 6),
            )

        if creature.species.name == "Predator" and creature.alive:
            font = pygame.font.SysFont("msgothic", 12)
            text = font.render("P", True, (255, 60, 60))
            screen.blit(text, (sx - 5, sy - size - 35))
