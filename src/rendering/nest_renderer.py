# nest_renderer.py
import pygame


class NestRenderer:
    @staticmethod
    def draw(world, screen, camera) -> None:
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

            fill = max(0.0, min(1.0, nest.stored_biomass / max(nest.max_storage, 1.0)))
            outer = (90, 45, 30)
            inner = (
                int(180 + fill * 60),
                int(90 + fill * 100),
                int(40 + fill * 30),
            )
            radius = 14 + int(fill * 10)
            pygame.draw.circle(screen, outer, (sx, sy), radius + 4, 2)
            pygame.draw.circle(screen, inner, (sx, sy), radius)
            pygame.draw.circle(screen, (255, 200, 120), (sx, sy), 5)

            members = nest_system.member_count(nest.id, nest.owner_species)
            if members > 0:
                font = pygame.font.SysFont("msgothic", 11)
                label = font.render(str(members), True, (255, 230, 200))
                screen.blit(label, (sx - 4, sy - radius - 16))
