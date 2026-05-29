# creature_renderer.py
import pygame

from src.utils.creature_helpers import get_haul_max_carry, hp_ratio, satiety_ratio
from src.utils.position_helpers import entity_xy

# コロニー種の頭上ラベル（勢力色）
COLONY_SPECIES_LABELS: dict[str, str] = {
    "red_ant": "R",
    "red_ant_soldier": "R",
    "blue_ant": "B",
    "blue_ant_soldier": "B",
    "yellow_ant": "Y",
    "yellow_ant_soldier": "Y",
}


class CreatureRenderer:
    """生物描画クラス（見えやすく強化）"""

    @staticmethod
    def draw(creature, screen, camera, *, is_selected: bool = False):
        cx, cy = entity_xy(creature)
        sx = int(cx - camera.x)
        sy = int(cy - camera.y)

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

        if is_selected:
            pygame.draw.circle(screen, (255, 240, 120), (sx, sy), size + 12, 2)
            pygame.draw.circle(screen, (255, 200, 80), (sx, sy), size + 16, 1)

        bar_w = int(size * 3.0)
        bar_x = sx - bar_w // 2

        if is_carcass:
            biomass = creature.biomass_ratio() if hasattr(creature, "biomass_ratio") else 0.0
            bar_y = sy - size - 22
            bar_color = CreatureRenderer._biomass_bar_color(biomass)
            pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, 7))
            pygame.draw.rect(
                screen, bar_color, (bar_x, bar_y, int(bar_w * biomass), 7)
            )
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

        colony = getattr(creature, "colony", None)
        colony_label = COLONY_SPECIES_LABELS.get(creature.species.name)
        if colony_label is not None and creature.alive:
            font = pygame.font.SysFont("msgothic", 12)
            label = colony_label
            label_color = tuple(creature.species.color)
            if colony is not None and colony.is_carrying:
                label = "↩"
                max_carry = max(get_haul_max_carry(creature), 0.001)
                chunk_ratio = min(1.0, colony.carried_biomass / max_carry)
                carcass = colony.carried_carcass
                prey_color = (120, 90, 70)
                if carcass is not None:
                    prey_color = tuple(max(0, c // 2) for c in carcass.species.color)
                csize = max(3, int(size * 0.35 + chunk_ratio * size * 0.45))
                pygame.draw.circle(
                    screen, prey_color, (sx + size + 6, sy), csize
                )
                pygame.draw.line(
                    screen,
                    (255, 200, 80),
                    (sx, sy),
                    (sx + size + 6, sy),
                    2,
                )
            text = font.render(label, True, label_color)
            screen.blit(text, (sx - 8, sy - size - 35))

    @staticmethod
    def _biomass_bar_color(ratio: float) -> tuple:
        """残存バイオマス 1.0→緑, 0.5→黄, 0.0→赤"""
        ratio = max(0.0, min(1.0, ratio))
        if ratio > 0.5:
            t = (ratio - 0.5) * 2.0
            return (int(255 * (1.0 - t)), 255, 0)
        t = ratio * 2.0
        return (255, int(255 * t), 0)
