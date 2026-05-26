# nest_renderer.py
import pygame


class NestRenderer:
    @staticmethod
    def draw(world, screen, camera, selected_nest_id: int | None = None) -> None:
        nest_system = getattr(world, "nest_system", None)
        if nest_system is None:
            return

        for nest in nest_system.nests.values():
            sx = int(nest.x - camera.x)
            sy = int(nest.y - camera.y)
            if not (
                -80 <= sx <= camera.screen_w + 80
                and -80 <= sy <= camera.screen_h + 80
            ):
                continue

            fill = nest.food_ratio
            outer = (90, 45, 30)
            inner = (
                int(180 + fill * 60),
                int(90 + fill * 100),
                int(40 + fill * 30),
            )
            radius = 14 + int(fill * 10)
            selected = selected_nest_id is not None and nest.id == selected_nest_id
            if selected:
                pygame.draw.circle(screen, (255, 240, 120), (sx, sy), radius + 10, 2)
            pygame.draw.circle(screen, outer, (sx, sy), radius + 4, 2)
            pygame.draw.circle(screen, inner, (sx, sy), radius)
            pygame.draw.circle(screen, (255, 200, 120), (sx, sy), 5)

            if fill > 0.05:
                leak_glow = (
                    int(40 + fill * 40),
                    int(120 + fill * 80),
                    int(180 + fill * 50),
                )
                pygame.draw.circle(
                    screen, leak_glow, (sx, sy), radius + 8, 1
                )

            members = nest_system.member_count(nest.id, nest.owner_species)
            font = pygame.font.SysFont("msgothic", 11)
            if members > 0:
                label = font.render(str(members), True, (255, 230, 200))
                screen.blit(label, (sx - 4, sy - radius - 16))
            if fill > 0.08:
                food_pct = int(fill * 100)
                food_label = font.render(f"食{food_pct}", True, (255, 210, 140))
                screen.blit(food_label, (sx - 10, sy + radius + 4))
