# nest_renderer.py
import pygame

# 種ごとの巣の見た目（owner_species → outer, inner, glow）
NEST_STYLE_BY_SPECIES: dict[str, dict[str, tuple[int, int, int]]] = {
    "Ant": {
        "outer": (90, 45, 30),
        "inner_base": (180, 90, 40),
        "glow_base": (40, 120, 180),
        "hole": (255, 230, 180),
    },
    "EnemyAnt": {
        "outer": (35, 45, 95),
        "inner_base": (70, 100, 200),
        "glow_base": (50, 80, 200),
        "hole": (180, 210, 255),
    },
}
DEFAULT_NEST_STYLE = NEST_STYLE_BY_SPECIES["Ant"]
NEST_OWNER_LABEL = {"Ant": "A", "EnemyAnt": "E"}


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
            style = NEST_STYLE_BY_SPECIES.get(nest.owner_species, DEFAULT_NEST_STYLE)
            outer = style["outer"]
            ib = style["inner_base"]
            inner = (
                int(ib[0] + fill * 60),
                int(ib[1] + fill * 100),
                int(ib[2] + fill * 30),
            )
            radius = 14 + int(fill * 10)
            selected = selected_nest_id is not None and nest.id == selected_nest_id
            if selected:
                pygame.draw.circle(screen, (255, 240, 120), (sx, sy), radius + 10, 2)
            pygame.draw.circle(screen, outer, (sx, sy), radius + 4, 2)
            pygame.draw.circle(screen, inner, (sx, sy), radius)
            center_dot = (
                int(min(255, ib[0] + 75)),
                int(min(255, ib[1] + 110)),
                int(min(255, ib[2] + 80)),
            )
            pygame.draw.circle(screen, center_dot, (sx, sy), 5)

            hole_fill = style["hole"]
            for h in getattr(nest, "holes", []) or []:
                hx = int(h.x - camera.x)
                hy = int(h.y - camera.y)
                pygame.draw.circle(screen, hole_fill, (hx, hy), 4)
                pygame.draw.circle(screen, outer, (hx, hy), 6, 1)

            if fill > 0.05:
                gb = style["glow_base"]
                leak_glow = (
                    int(gb[0] + fill * 40),
                    int(gb[1] + fill * 80),
                    int(gb[2] + fill * 50),
                )
                pygame.draw.circle(
                    screen, leak_glow, (sx, sy), radius + 8, 1
                )

            members = nest_system.member_count(nest.id, nest.owner_species)
            font = pygame.font.SysFont("msgothic", 11)
            owner_tag = NEST_OWNER_LABEL.get(nest.owner_species)
            if owner_tag is not None:
                tag_surf = font.render(owner_tag, True, (255, 245, 220))
                screen.blit(tag_surf, (sx - 4, sy + radius + 2))
            if members > 0:
                label = font.render(str(members), True, (255, 230, 200))
                screen.blit(label, (sx - 4, sy - radius - 16))
            if fill > 0.08:
                food_pct = int(fill * 100)
                food_label = font.render(f"食{food_pct}", True, (255, 210, 140))
                screen.blit(food_label, (sx - 10, sy + radius + 4))
