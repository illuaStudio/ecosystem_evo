# creature_renderer.py
import pygame

from creature_helpers import energy_ratio


class CreatureRenderer:
    """生物描画クラス（見えやすく強化）"""

    @staticmethod
    def draw(creature, screen, camera):
        # 画面外なら描画しない
        sx = int(creature.pos[0] - camera.x)
        sy = int(creature.pos[1] - camera.y)

        if not (0 - 50 <= sx <= camera.screen_w + 50 and 0 - 50 <= sy <= camera.screen_h + 50):
            return

        color = creature.species.color
        size = int(creature.traits.get("base_size", 8))

        # 軌跡（移動していたら）
        if hasattr(creature, 'last_pos'):
            lx = int(creature.last_pos[0] - camera.x)
            ly = int(creature.last_pos[1] - camera.y)
            if abs(lx - sx) + abs(ly - sy) > 2:
                trail_color = (max(0, color[0]-80), max(0, color[1]-80), max(0, color[2]-80))
                pygame.draw.line(screen, trail_color, (lx, ly), (sx, sy), max(2, size//2))

        # 本体
        pygame.draw.circle(screen, color, (sx, sy), size + 2)
        pygame.draw.circle(screen, (255, 255, 255), (sx, sy), size + 2, 2)  # 白枠を太く

        # エネルギーバー
        bar_w = int(size * 3.0)
        fill_ratio = energy_ratio(creature)
        bar_x = sx - bar_w // 2
        bar_y = sy - size - 22

        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, 8))
        pygame.draw.rect(screen, (80 + int(fill_ratio * 175), 255, 80),
                        (bar_x, bar_y, int(bar_w * fill_ratio), 8))

        # 種名表示（デバッグ用、小さく）
        if creature.species.name == "Predator":
            font = pygame.font.SysFont("msgothic", 12)
            text = font.render("P", True, (255, 60, 60))
            screen.blit(text, (sx - 5, sy - size - 35))