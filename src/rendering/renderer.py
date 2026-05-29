# renderer.py
import pygame

from src.config import config
from src.ai.actions import SplitAction
from src.rendering.nest_renderer import NestRenderer
from src.utils.creature_helpers import (
    count_alive_by_species,
    current_size,
    format_carry_status,
    format_individual_trait_lines,
    format_nutrition_status,
    format_life_stage_line,
    get_haul_max_carry,
    get_species_population_cap,
    satiety_ratio,
)
from src.utils.hunt_helpers import (
    describe_creature_short,
    find_attackers_for_target,
    get_aggression_target,
    get_combat_target,
    get_hunt_target,
)
from src.utils.position_helpers import entity_xy


class Renderer:
    """描画専用クラス"""

    # ワールド外・余白（画面 > マップ時）と HUD 背面
    UI_MARGIN_COLOR = (14, 22, 14)
    UI_PANEL_COLOR = (0, 0, 0, 170)
    HUD_TOP_HEIGHT = 118
    HUD_TOP_HEIGHT_DEBUG = 138
    HUD_LEFT_PANEL_WIDTH = 520
    HUD_RIGHT_PANEL_WIDTH = 220

    def __init__(self, screen, font, small_font, big_font):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.big_font = big_font
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None

    def draw(
        self,
        creatures,
        camera,
        selected_creature,
        selected_nest,
        paused,
        show_debug=False,
        map_view_mode="biome",
        show_territory=False,
    ):
        self._show_territory_hud = show_territory
        # 毎フレーム必ず全画面クリア（未描画領域に UI が残るのを防ぐ）
        self.screen.fill(self.UI_MARGIN_COLOR)

        world = getattr(camera, "world", None)
        self._draw_background(world, camera, map_view_mode)

        if world is not None:
            nest_id = selected_nest.id if selected_nest is not None else None
            NestRenderer.draw_territories(
                world,
                self.screen,
                camera,
                show_territory=show_territory,
                selected_nest_id=nest_id,
            )
            NestRenderer.draw(world, self.screen, camera, nest_id)

        for c in creatures:
            if hasattr(c, "draw"):
                c.draw(
                    self.screen,
                    camera,
                    is_selected=(
                        selected_creature is not None and c is selected_creature
                    ),
                )

        if world is not None and selected_creature is not None:
            self._draw_hunt_overlays(world, camera, selected_creature)

        has_selection = selected_creature is not None or selected_nest is not None
        self._draw_hud_panels(has_selection=has_selection, show_debug=show_debug)

        if selected_creature:
            y = 130
            sc = selected_creature
            action_name = sc.current_action.__class__.__name__ if sc.current_action else "None"

            self.screen.blit(self.font.render("【選択中の個体】", True, (255, 220, 100)), (15, y))
            y += 35

            status = "死骸" if not sc.alive else "生存"
            texts = [
                f"種: {sc.species.name} ({status})",
                f"HP: {sc.hp:.1f}/{sc.max_hp:.0f}",
                format_nutrition_status(sc) if sc.alive else f"満腹度: {sc.satiety:.1f}/{sc.max_satiety:.0f}",
                f"サイズ: {sc.get_current_size():.1f} / {sc.traits.get('max_size', sc.get_current_size()):.1f}",
                f"年齢: {sc.age}",
                f"速度: {sc.get_current_speed():.2f}",
                f"現在のAction: {action_name}",
            ]
            life_line = format_life_stage_line(sc)
            if life_line:
                texts.insert(4, life_line)
            trait_lines = format_individual_trait_lines(sc)
            if trait_lines:
                texts.append("個体特性 (基本値との差):")
                texts.extend(trait_lines)
            if not sc.alive:
                texts.insert(
                    3,
                    f"バイオマス: {sc.remaining_biomass:.1f}/{sc.initial_biomass:.1f} "
                    f"({sc.biomass_ratio() * 100:.0f}%)",
                )
            if world and sc.alive:
                sx, sy = entity_xy(sc)
                biome = world.get_biome_at(sx, sy)
                texts.append(
                    f"バイオーム: {biome.get('display_name', biome.get('name', '?'))}"
                )
                if hasattr(world, "get_mana_density"):
                    density = world.get_mana_density(sx, sy)
                    cap = getattr(world, "mana_density_cap", 2500.0)
                    texts.append(f"マナ残量: {density:.0f}/{cap:.0f}")

            # 分裂（SplitAction）の条件可視化：調整時に「そもそも条件を満たしていない」を即判別する
            if sc.alive:
                action_defs = (getattr(sc.species, "mind_data", {}) or {}).get("actions", [])
                split_def = next(
                    (a for a in action_defs if a.get("name") == "SplitAction"),
                    None,
                )
                if split_def is not None:
                    p = dict(SplitAction.DEFAULT_PARAMS)
                    p.update(split_def.get("params", {}) or {})

                    mature_age = sc.life_cycle.get("mature")
                    size_now = current_size(sc)
                    sat_now = satiety_ratio(sc)
                    cd_ok = getattr(sc, "repro_cooldown", 0) <= 0
                    mature_ok = mature_age is not None and sc.age >= int(mature_age)
                    size_ok = size_now >= float(p["min_reproduce_size"])
                    sat_ok = sat_now >= float(p["satiety_threshold"])
                    cap = None
                    if getattr(sc, "world", None) is not None:
                        cap = get_species_population_cap(sc.world, sc.species.name)

                    alive = 0
                    pop_ok = True
                    if cap is not None and getattr(sc, "world", None) is not None:
                        alive = count_alive_by_species(sc.world, sc.species.name)
                        pop_ok = alive < cap

                    if (
                        cd_ok
                        and mature_ok
                        and size_ok
                        and sat_ok
                        and pop_ok
                        and getattr(sc, "world", None) is not None
                    ):
                        texts.append(
                            "分裂条件(Split): OK"
                            f"（サイズ≥{float(p['min_reproduce_size']):.1f}, 満腹≥{float(p['satiety_threshold']):.2f}）"
                        )
                    else:
                        reasons: list[str] = []
                        if getattr(sc, "world", None) is None:
                            reasons.append("worldなし")
                        if not cd_ok:
                            reasons.append(f"cooldown {int(sc.repro_cooldown)}")
                        if not mature_ok:
                            if mature_age is None:
                                reasons.append("mature未定義")
                            else:
                                reasons.append(f"成熟 age {sc.age} < {int(mature_age)}")
                        if not size_ok:
                            reasons.append(
                                f"サイズ {size_now:.1f} < {float(p['min_reproduce_size']):.1f}"
                            )
                        if not sat_ok:
                            reasons.append(
                                f"満腹 {sat_now:.2f} < {float(p['satiety_threshold']):.2f}"
                            )
                        if not pop_ok and cap is not None:
                            reasons.append(
                                f"種族上限 {alive}/{cap}"
                            )
                        texts.append("分裂条件(Split): NG → " + " / ".join(reasons))
            colony = getattr(sc, "colony", None)
            if colony is not None and world is not None:
                nest = world.nest_system.get_creature_nest(sc)
                if nest is not None:
                    texts.append(
                        f"巣 #{nest.id}: 食料 {nest.stored_food:.0f}/{nest.max_food:.0f}"
                    )
                    texts.append(
                        f"  備蓄率 {nest.food_ratio * 100:.0f}%"
                        "（余剰はマナへ漏洩）"
                    )
                    texts.append(
                        f"コロニー: {world.nest_system.total_member_count(nest.id)} 匹"
                    )
                    from src.utils.creature_helpers import get_territory_radius_for_nest

                    texts.append(
                        f"テリトリー半径: {get_territory_radius_for_nest(world, nest):.0f} px"
                    )
                carry_line = format_carry_status(sc)
                if carry_line is not None:
                    texts.append(carry_line)
                if sc.alive and not colony.is_carrying:
                    texts.append(
                        f"持ち帰り上限(base_max_carry): {get_haul_max_carry(sc):.1f}"
                    )

            hunt_target = get_hunt_target(sc)
            combat_target = get_combat_target(sc)
            if combat_target is not None:
                texts.append(
                    f"戦闘対象: {describe_creature_short(combat_target)}"
                )
            elif hunt_target is not None:
                texts.append(
                    f"狩り対象: {describe_creature_short(hunt_target)}"
                )
            elif sc.alive and sc.current_action is not None:
                action_name = sc.current_action.__class__.__name__
                if action_name == "CombatAction":
                    texts.append("戦闘対象: （未確定／視界外）")
                elif action_name == "HuntAction":
                    texts.append("狩り対象: （未確定／視界外）")

            if sc.alive:
                attackers = find_attackers_for_target(world, sc)
                if attackers:
                    texts.append(f"狙われ中: {len(attackers)} 匹")
                    for attacker in attackers[:5]:
                        texts.append(f"  ← {describe_creature_short(attacker)}")
                    if len(attackers) > 5:
                        texts.append(f"  …他 {len(attackers) - 5} 匹")

            for text in texts:
                self.screen.blit(self.small_font.render(text, True, (255, 255, 255)), (15, y))
                y += 24

        elif selected_nest is not None and world is not None:
            y = self._draw_nest_detail_panel(selected_nest, world, y=130)

        status = "【PAUSED】" if paused else "実行中"
        self.screen.blit(
            self.big_font.render(
                f"{config.game['game_title']} v{config.game['version']}   {status}",
                True,
                (200, 255, 200),
            ),
            (15, 10),
        )

        mana_label = ""
        if world:
            w = world
            mult = getattr(w, "avg_mana_regen_multiplier", 1.0)
            view_name = "マナ密度" if map_view_mode == "mana" else "バイオーム"
            territory_on = getattr(self, "_show_territory_hud", False)
            territory_label = "  テリトリー: ON" if territory_on else ""
            mana_label = (
                f"    Mana: {w.mana:.0f}/{w.max_mana:.0f}  (回復×{mult:.2f})"
                f"    表示: {view_name}{territory_label}"
            )
        self.screen.blit(
            self.font.render(f"生き物: {len(creatures):3d} 匹{mana_label}", True, (230, 245, 210)),
            (15, 55),
        )

        if world is not None:
            self._draw_population_panel(world)

        self.screen.blit(
            self.small_font.render(
                "Space:停止/再開  R:リセット  M:表示切替  T:テリトリー  A:アメーバ  S:クモ  P:味方アリ  H:巣穴  右クリック:個体/巣",
                True,
                (160, 200, 255),
            ),
            (15, 85),
        )

        if show_debug and world:
            debug_text = self.small_font.render(
                f"Debug | 生物: {len(creatures)} | マナ回復平均倍率: {world.avg_mana_regen_multiplier:.3f}",
                True,
                (255, 255, 100),
            )
            self.screen.blit(debug_text, (15, 110))

    def _draw_population_panel(self, world) -> None:
        """ワールド population_limits の現在数 / 上限を右上に表示。"""
        limits = getattr(world, "population_limits", None) or {}
        if not limits:
            return

        lines = ["【個体数】"]
        for species_name in sorted(limits.keys()):
            cap = limits[species_name]
            alive = count_alive_by_species(world, species_name)
            at_cap = alive >= cap
            color = (255, 180, 140) if at_cap else (200, 230, 200)
            text = f"{species_name}: {alive} / {cap}"
            lines.append((text, color))

        margin_x = 12
        y = 10
        for i, item in enumerate(lines):
            if i == 0:
                surf = self.font.render(item, True, (220, 235, 200))
            else:
                text, color = item
                surf = self.small_font.render(text, True, color)
            x = self.screen.get_width() - surf.get_width() - margin_x
            self.screen.blit(surf, (x, y))
            y += surf.get_height() + 4

    def _draw_hunt_overlays(self, world, camera, selected_creature) -> None:
        """選択個体と狩り・戦闘関係の線・ターゲットマーカー。"""
        sc = selected_creature
        combat_target = get_combat_target(sc)
        hunt_target = get_hunt_target(sc)
        if combat_target is not None:
            self._draw_hunt_link(sc, combat_target, camera, (120, 160, 255))
            self._draw_prey_marker(combat_target, camera, (100, 140, 255))
        elif hunt_target is not None:
            self._draw_hunt_link(sc, hunt_target, camera, (255, 90, 90))
            self._draw_prey_marker(hunt_target, camera, (255, 120, 80))

        attackers = find_attackers_for_target(world, sc)
        for attacker in attackers:
            link_color = (80, 120, 255) if get_combat_target(attacker) is sc else (255, 60, 60)
            self._draw_hunt_link(attacker, sc, camera, link_color)
            hx, hy = entity_xy(attacker)
            hsx = int(hx - camera.x)
            hsy = int(hy - camera.y)
            hsize = int(attacker.traits.get("base_size", 8))
            pygame.draw.circle(
                self.screen, (255, 100, 100), (hsx, hsy), hsize + 14, 2
            )

    def _draw_hunt_link(
        self, predator, prey, camera, color: tuple[int, int, int]
    ) -> None:
        px, py = entity_xy(predator)
        tx, ty = entity_xy(prey)
        sx1, sy1 = int(px - camera.x), int(py - camera.y)
        sx2, sy2 = int(tx - camera.x), int(ty - camera.y)
        pygame.draw.line(self.screen, color, (sx1, sy1), (sx2, sy2), 2)
        mid_x, mid_y = (sx1 + sx2) // 2, (sy1 + sy2) // 2
        pygame.draw.circle(self.screen, color, (mid_x, mid_y), 4)

    def _draw_prey_marker(self, prey, camera, color: tuple[int, int, int]) -> None:
        tx, ty = entity_xy(prey)
        sx = int(tx - camera.x)
        sy = int(ty - camera.y)
        size = int(prey.traits.get("base_size", 9))
        pygame.draw.circle(self.screen, color, (sx, sy), size + 14, 2)
        pygame.draw.circle(self.screen, (255, 240, 180), (sx, sy), size + 18, 1)
        font = pygame.font.SysFont("msgothic", 12)
        label = font.render("TARGET", True, (255, 220, 160))
        self.screen.blit(label, (sx - 22, sy - size - 32))

    def _draw_nest_detail_panel(self, nest, world, y: int = 130) -> int:
        """選択中の巣の詳細 HUD。戻り値は次の描画 Y。"""
        from src.config import config

        ns = world.nest_system
        species_data = config.get_species(nest.owner_species) or {}
        colony_cfg = species_data.get("colony", {})
        members = ns.member_count(nest.id, nest.owner_species)
        can_spawn, spawn_msg = ns.spawn_readiness(nest)

        cost = float(colony_cfg.get("spawn_food_cost", 0))
        reserve = float(colony_cfg.get("min_food_reserve", 0))
        max_workers = int(colony_cfg.get("max_workers", 0))
        max_pop = get_species_population_cap(world, nest.owner_species)
        leak_rate = float(colony_cfg.get("food_leak_rate", 0))

        self.screen.blit(
            self.font.render("【選択中の巣】", True, (255, 200, 120)), (15, y)
        )
        y += 35

        texts = [
            f"巣 #{nest.id}  ({nest.owner_species})",
            f"位置: ({nest.x:.0f}, {nest.y:.0f})",
            f"巣穴: {len(getattr(nest, 'holes', []) or [])} 個  (H:カーソル位置に追加)",
            f"食料: {nest.stored_food:.1f} / {nest.max_food:.0f}",
            f"備蓄率: {nest.food_ratio * 100:.1f}%",
            f"コロニー: {members} 匹",
            f"繁殖: {spawn_msg}",
        ]
        if cost > 0:
            cap_note = f" / 種族上限 {max_pop}" if max_pop else ""
            texts.append(
                f"  1回 {cost:.0f} 消費 / 最低備蓄 {reserve:.0f} / 巣 {max_workers} 匹{cap_note}"
            )
        if leak_rate > 0:
            texts.append(f"  漏洩率: {leak_rate:.5f}/tick（余剰→マナ）")

        for text in texts:
            if text.startswith("繁殖:"):
                color = (180, 255, 180) if can_spawn else (255, 220, 180)
            else:
                color = (255, 255, 255)
            self.screen.blit(self.small_font.render(text, True, color), (15, y))
            y += 24

        return y

    def _get_ui_panel(self) -> pygame.Surface:
        sw, sh = self.screen.get_size()
        if self._ui_panel is None or self._ui_panel.get_size() != (sw, sh):
            self._ui_panel = pygame.Surface((sw, sh), pygame.SRCALPHA)
        return self._ui_panel

    def _draw_hud_panels(self, has_selection: bool, show_debug: bool) -> None:
        """HUD テキストの背面を塗り、前フレームの文字残りを防ぐ。"""
        panel = self._get_ui_panel()
        panel.fill((0, 0, 0, 0))

        sw, sh = self.screen.get_size()
        top_h = self.HUD_TOP_HEIGHT if not show_debug else self.HUD_TOP_HEIGHT_DEBUG
        pygame.draw.rect(panel, self.UI_PANEL_COLOR, (0, 0, sw, top_h))

        if has_selection:
            left_w = min(self.HUD_LEFT_PANEL_WIDTH, sw)
            pygame.draw.rect(panel, self.UI_PANEL_COLOR, (0, top_h, left_w, sh - top_h))

        self.screen.blit(panel, (0, 0))

    def _draw_background(self, world, camera, map_view_mode="biome") -> None:
        if world is None:
            return

        if map_view_mode == "mana" and getattr(world, "mana_density", None):
            self._draw_mana_density_tiles(world, camera)
        elif world.biome_color_grid:
            self._draw_biome_tiles(world, camera)
        else:
            self._draw_world_rect(world, camera, world.background_color)

    def _ensure_biome_surface(self, world) -> None:
        """ワールド全体のバイオーム地面を1枚の Surface に焼き付け（初回のみ）。"""
        wid = id(world)
        if self._biome_surface_world_id == wid and self._biome_surface is not None:
            return

        cell = world.biome_cell_size
        surface = pygame.Surface((world.width, world.height))
        grid = world.biome_color_grid

        for row, row_colors in enumerate(grid):
            wy = row * cell
            rh = min(cell, world.height - wy)
            if rh <= 0:
                continue
            for col, color in enumerate(row_colors):
                wx = col * cell
                rw = min(cell, world.width - wx)
                if rw <= 0:
                    continue
                surface.fill(color, (wx, wy, rw, rh))

        self._biome_surface = surface
        self._biome_surface_world_id = wid

    def _draw_world_rect(self, world, camera, color) -> None:
        """ワールド範囲だけ単色で塗る（マップが画面より小さいときの余白は残す）。"""
        cam_x = int(camera.x)
        cam_y = int(camera.y)
        dest = pygame.Rect(-cam_x, -cam_y, world.width, world.height)
        visible = dest.clip(self.screen.get_rect())
        if visible.width > 0 and visible.height > 0:
            pygame.draw.rect(self.screen, color, visible)

    def _draw_biome_tiles(self, world, camera) -> None:
        self._ensure_biome_surface(world)
        cam_x = int(camera.x)
        cam_y = int(camera.y)
        sw, sh = self.screen.get_width(), self.screen.get_height()

        src = pygame.Rect(cam_x, cam_y, sw, sh)
        src.clamp_ip(self._biome_surface.get_rect())
        if src.width <= 0 or src.height <= 0:
            return

        dest = pygame.Rect(src.x - cam_x, src.y - cam_y, src.width, src.height)
        self.screen.blit(self._biome_surface, dest, src)

    @staticmethod
    def _mana_density_to_color(density: float, cap: float) -> tuple[int, int, int]:
        """マナ残量をヒートマップ色（低=暗紫、高=明るいシアン）に変換。"""
        if cap <= 0:
            return (30, 20, 50)
        t = max(0.0, min(1.0, density / cap))
        r = int(28 + t * 80)
        g = int(18 + t * 200)
        b = int(48 + t * 207)
        return (r, g, b)

    def _draw_mana_density_tiles(self, world, camera) -> None:
        """可視範囲のマナ密度セルをヒートマップ表示（毎フレーム更新）。"""
        cell = world.mana_cell_size
        cap = world.mana_density_cap
        cam_x = int(camera.x)
        cam_y = int(camera.y)
        sw, sh = self.screen.get_width(), self.screen.get_height()

        start_col = max(0, cam_x // cell)
        end_col = min(world._mana_cols, (cam_x + sw + cell - 1) // cell + 1)
        start_row = max(0, cam_y // cell)
        end_row = min(world._mana_rows, (cam_y + sh + cell - 1) // cell + 1)

        screen_rect = self.screen.get_rect()
        for row in range(start_row, end_row):
            wy = row * cell
            screen_y = wy - cam_y
            rh = min(cell, world.height - wy)
            for col in range(start_col, end_col):
                wx = col * cell
                screen_x = wx - cam_x
                rw = min(cell, world.width - wx)
                density = world.mana_density[row][col]
                color = self._mana_density_to_color(density, cap)
                rect = pygame.Rect(screen_x, screen_y, rw, rh)
                visible = rect.clip(screen_rect)
                if visible.width > 0 and visible.height > 0:
                    pygame.draw.rect(self.screen, color, visible)

    def invalidate_biome_cache(self) -> None:
        """ワールドリセット時に呼ぶ（SimulationEngine.reset_simulation から）。"""
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None
