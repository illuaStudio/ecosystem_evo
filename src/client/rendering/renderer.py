# renderer.py
import pygame

from src.config import config
from src.sim.ai.actions import SplitAction
from src.client.rendering.field_emitter_renderer import FieldEmitterRenderer
from src.client.rendering.creature_renderer import CreatureRenderer
from src.client.rendering.nest_renderer import NestRenderer
from src.sim.utils.creature_helpers import (
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
from src.sim.utils.hunt_helpers import (
    describe_creature_short,
    find_attackers_for_target,
    get_aggression_target,
    get_combat_target,
    get_hunt_target,
)
from src.client.species_visibility import SpeciesVisibilityManager, VisibilityToggleRect
from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.position_helpers import entity_xy


class Renderer:
    """描画専用クラス"""

    # ワールド外・余白（画面 > マップ時）と HUD 背面
    UI_MARGIN_COLOR = (14, 22, 14)
    UI_PANEL_COLOR = (0, 0, 0, 170)
    HUD_TOP_HEIGHT = 118
    HUD_TOP_HEIGHT_DEBUG = 138
    HUD_LEFT_PANEL_WIDTH = 520
    HUD_RIGHT_PANEL_WIDTH = 220
    HUD_VISIBILITY_PANEL_WIDTH = 200

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
        show_sheltered=False,
        user_message: str = "",
        message_feed=None,
        player_colony_id: str = "",
        game_state=None,
        species_visibility: SpeciesVisibilityManager | None = None,
    ):
        self._show_territory_hud = show_territory
        self._show_sheltered_hud = show_sheltered
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
            FieldEmitterRenderer.draw(world, self.screen, camera)
            if show_territory and selected_nest is not None:
                import pygame as _pg

                mx, my = _pg.mouse.get_pos()
                NestRenderer.draw_hole_placement_preview(
                    world,
                    self.screen,
                    camera,
                    selected_nest,
                    mx + camera.x,
                    my + camera.y,
                )

        for c in creatures:
            if species_visibility is not None and not species_visibility.is_creature_visible(c):
                continue
            if is_creature_sheltered(c) and not show_sheltered:
                continue
            CreatureRenderer.draw(
                c,
                self.screen,
                camera,
                is_selected=(
                    selected_creature is not None and c is selected_creature
                ),
                show_sheltered_debug=show_sheltered,
            )

        if (
            world is not None
            and selected_creature is not None
            and (
                not is_creature_sheltered(selected_creature) or show_sheltered
            )
            and (
                species_visibility is None
                or species_visibility.is_creature_visible(selected_creature)
            )
        ):
            self._draw_hunt_overlays(
                world, camera, selected_creature, species_visibility
            )

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
            if is_creature_sheltered(sc):
                texts.insert(1, "状態: 巣内")
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
                biome = world.biome.get_biome_at(sx, sy)
                texts.append(
                    f"バイオーム: {biome.get('display_name', biome.get('name', '?'))}"
                )
                ml = world.mana_layer
                density = ml.get_mana_density(sx, sy)
                cap = getattr(ml, "mana_density_cap", 2500.0)
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
                    from src.sim.utils.creature_helpers import get_territory_radius_for_nest

                    hole_n = len(getattr(nest, "holes", []) or [])
                    texts.append(
                        f"勢力 {nest.colony_id} | テリトリー半径 "
                        f"{get_territory_radius_for_nest(world, nest):.0f} px | 巣穴 {hole_n}"
                    )
                carry_line = format_carry_status(sc)
                if carry_line is not None:
                    texts.append(carry_line)
                from src.sim.utils.inventory_helpers import inventory_is_loaded

                if sc.alive and not inventory_is_loaded(sc) and getattr(sc, "inventory", None):
                    inv = sc.inventory
                    if inv.slot_count > 0:
                        texts.append(
                            f"インベントリ先頭枠上限: {inv.slot_max_mass(0):.1f}"
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
                f"{config.game_app['game_title']} v{config.game_app['version']}   {status}",
                True,
                (200, 255, 200),
            ),
            (15, 10),
        )

        mana_label = ""
        if world:
            ml = world.mana_layer
            mult = world.biome.avg_mana_regen_multiplier
            view_name = "マナ密度" if map_view_mode == "mana" else "バイオーム"
            territory_on = getattr(self, "_show_territory_hud", False)
            sheltered_on = getattr(self, "_show_sheltered_hud", False)
            territory_label = "  テリトリー: ON" if territory_on else ""
            sheltered_label = "  巣内: ON" if sheltered_on else ""
            mana_label = (
                f"    Mana: {ml.mana:.0f}/{ml.max_mana:.0f}  (回復×{mult:.2f})"
                f"    表示: {view_name}{territory_label}{sheltered_label}"
            )
        visible_count = len(creatures)
        if species_visibility is not None:
            visible_count = sum(
                1 for c in creatures if species_visibility.is_creature_visible(c)
            )
        count_label = f"表示: {visible_count:3d} / 全 {len(creatures):3d} 匹"
        self.screen.blit(
            self.font.render(f"{count_label}{mana_label}", True, (230, 245, 210)),
            (15, 55),
        )

        if world is not None:
            self._draw_population_panel(world)
            if player_colony_id:
                self._draw_queen_status_panel(world, player_colony_id, game_state)
            if species_visibility is not None:
                self._draw_visibility_panel(world, species_visibility, creatures)

        if user_message:
            self.screen.blit(
                self.font.render(user_message, True, (255, 230, 140)),
                (15, 118),
            )

        if message_feed is not None:
            self._draw_message_feed(message_feed)

        self.screen.blit(
            self.small_font.render(
                "Space:停止/再開  R:リセット  M:表示切替  T:テリトリー  I:巣内表示  1〜5:生態表示  右クリ:個体/巣  右下:表示パネル",
                True,
                (160, 200, 255),
            ),
            (15, 85),
        )

        if show_debug and world:
            debug_text = self.small_font.render(
                f"Debug | 生物: {len(creatures)} | マナ回復平均倍率: {world.biome.avg_mana_regen_multiplier:.3f}",
                True,
                (255, 255, 100),
            )
            self.screen.blit(debug_text, (15, 110))

    def _draw_message_feed(self, message_feed) -> None:
        """左下: ゲーム進行・イベントメッセージ履歴。"""
        entries = message_feed.entries()
        if not entries:
            return

        margin = 12
        panel_w = min(520, self.screen.get_width() - margin * 2)
        line_h = 20
        header_h = 24
        panel_h = header_h + len(entries) * line_h + 10
        sw, sh = self.screen.get_size()
        x0 = margin
        y0 = sh - panel_h - margin

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill(self.UI_PANEL_COLOR)
        self.screen.blit(bg, (x0, y0))

        self.screen.blit(
            self.small_font.render("【メッセージ】", True, (220, 235, 200)),
            (x0 + 8, y0 + 4),
        )

        y = y0 + header_h
        for entry in entries:
            text = entry.text
            if len(text) > 56:
                text = text[:53] + "..."
            surf = self.small_font.render(text, True, entry.color)
            self.screen.blit(surf, (x0 + 8, y))
            y += line_h

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

    def _draw_queen_status_panel(self, world, player_colony_id: str, game_state) -> None:
        """右上（個体数パネル下）: プレイヤー女王の状態。"""
        from src.client.queen_status import build_queen_panel_lines

        lines = build_queen_panel_lines(world, player_colony_id, game_state)
        if not lines:
            return

        limits = getattr(world, "population_limits", None) or {}
        pop_lines = 1 + len(limits)
        y = 10 + pop_lines * 24 + 8

        margin_x = 12
        panel_w = 300
        line_h = 20
        panel_h = len(lines) * line_h + 10
        sw = self.screen.get_width()
        x0 = sw - panel_w - margin_x

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill(self.UI_PANEL_COLOR)
        self.screen.blit(bg, (x0, y))

        for i, (text, color) in enumerate(lines):
            if len(text) > 34:
                text = text[:31] + "..."
            surf = self.small_font.render(text, True, color)
            self.screen.blit(surf, (x0 + 8, y + 4 + i * line_h))

    def _draw_visibility_panel(
        self, world, visibility: SpeciesVisibilityManager, creatures
    ) -> None:
        """右下: 生態グループの表示 ON/OFF（クリックで切替）。"""
        groups = visibility.groups_for_world(world)
        if not groups:
            visibility.set_toggle_rects([])
            return

        margin = 12
        row_h = 24
        panel_w = self.HUD_VISIBILITY_PANEL_WIDTH
        header_h = 26
        panel_h = header_h + len(groups) * row_h + 10
        sw, sh = self.screen.get_size()
        x0 = sw - panel_w - margin
        y0 = sh - panel_h - margin

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 175))
        self.screen.blit(bg, (x0, y0))

        self.screen.blit(
            self.small_font.render("【表示】", True, (220, 235, 200)),
            (x0 + 8, y0 + 4),
        )

        hotkey_map = {
            "amoeba": "1",
            "red_ant": "2",
            "blue_ant": "3",
            "yellow_ant": "4",
            "spider": "5",
        }
        toggle_rects: list[VisibilityToggleRect] = []
        y = y0 + header_h
        for group_id, label, _names in groups:
            on = visibility.is_group_visible(group_id)
            color = visibility.representative_color(group_id)
            row_rect = (x0 + 4, y, panel_w - 8, row_h - 2)
            toggle_rects.append(VisibilityToggleRect(group_id, row_rect))

            pygame.draw.rect(self.screen, (50, 55, 50), row_rect, border_radius=3)
            pygame.draw.circle(self.screen, color, (row_rect[0] + 12, y + 10), 7)
            pygame.draw.circle(self.screen, (240, 240, 240), (row_rect[0] + 12, y + 10), 7, 1)

            key = hotkey_map.get(group_id, "")
            key_s = f"[{key}] " if key else ""
            state = "ON " if on else "OFF"
            text_color = (200, 255, 200) if on else (140, 140, 140)
            text = f"{key_s}{label}: {state}"
            self.screen.blit(
                self.small_font.render(text, True, text_color),
                (row_rect[0] + 26, y + 3),
            )
            y += row_h

        visibility.set_toggle_rects(toggle_rects)

    def _creature_visible_for_overlay(
        self, creature, species_visibility: SpeciesVisibilityManager | None
    ) -> bool:
        if creature is None:
            return False
        if species_visibility is None:
            return True
        return species_visibility.is_creature_visible(creature)

    def _draw_hunt_overlays(
        self,
        world,
        camera,
        selected_creature,
        species_visibility: SpeciesVisibilityManager | None = None,
    ) -> None:
        """選択個体と狩り・戦闘関係の線・ターゲットマーカー。"""
        sc = selected_creature
        combat_target = get_combat_target(sc)
        hunt_target = get_hunt_target(sc)
        if combat_target is not None and self._creature_visible_for_overlay(
            combat_target, species_visibility
        ):
            self._draw_hunt_link(sc, combat_target, camera, (120, 160, 255))
            self._draw_prey_marker(combat_target, camera, (100, 140, 255))
        elif hunt_target is not None and self._creature_visible_for_overlay(
            hunt_target, species_visibility
        ):
            self._draw_hunt_link(sc, hunt_target, camera, (255, 90, 90))
            self._draw_prey_marker(hunt_target, camera, (255, 120, 80))

        attackers = find_attackers_for_target(world, sc)
        for attacker in attackers:
            if not self._creature_visible_for_overlay(attacker, species_visibility):
                continue
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
        from src.sim.utils.colony_config_helpers import get_colony_profile

        ns = world.nest_system
        total = ns.total_member_count(nest.id)

        leak_per_tick = float(
            get_colony_profile(world, nest.colony_id).get("food_leak_per_tick", 0)
        )

        self.screen.blit(
            self.font.render("【選択中の巣】", True, (255, 200, 120)), (15, y)
        )
        y += 35

        colony_world = getattr(world, "colony_settings", {}) or {}
        hole_cost = float(colony_world.get("hole_food_cost", 250))
        max_holes = int(colony_world.get("max_holes", 8))
        hole_count = len(getattr(nest, "holes", []) or [])

        texts = [
            f"巣 #{nest.id}  勢力:{nest.colony_id}  種:{nest.owner_species}",
            f"位置: ({nest.x:.0f}, {nest.y:.0f})",
            f"巣穴: {hole_count}/{max_holes}  (H:カーソルに設置 / 費用 {hole_cost:.0f})",
            f"食料: {nest.stored_food:.1f} / {nest.max_food:.0f}",
            f"備蓄率: {nest.food_ratio * 100:.1f}%",
            f"コロニー: {total} 匹",
        ]
        if leak_per_tick > 0:
            texts.append(f"  漏洩: {leak_per_tick:.2f}/tick（余剰→マナ）")

        for text in texts:
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

        if map_view_mode == "mana" and getattr(world.mana_layer, "mana_density", None):
            self._draw_mana_density_tiles(world, camera)
        elif world.biome.biome_color_grid:
            self._draw_biome_tiles(world, camera)
        else:
            self._draw_world_rect(world, camera, world.background_color)

    def _ensure_biome_surface(self, world) -> None:
        """ワールド全体のバイオーム地面を1枚の Surface に焼き付け（初回のみ）。"""
        wid = id(world)
        if self._biome_surface_world_id == wid and self._biome_surface is not None:
            return

        cell = world.biome.biome_cell_size
        surface = pygame.Surface((world.width, world.height))
        grid = world.biome.biome_color_grid

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
        ml = world.mana_layer
        cell = ml.mana_cell_size
        cap = ml.mana_density_cap
        cam_x = int(camera.x)
        cam_y = int(camera.y)
        sw, sh = self.screen.get_width(), self.screen.get_height()

        start_col = max(0, cam_x // cell)
        end_col = min(ml._mana_cols, (cam_x + sw + cell - 1) // cell + 1)
        start_row = max(0, cam_y // cell)
        end_row = min(ml._mana_rows, (cam_y + sh + cell - 1) // cell + 1)

        screen_rect = self.screen.get_rect()
        for row in range(start_row, end_row):
            wy = row * cell
            screen_y = wy - cam_y
            rh = min(cell, world.height - wy)
            for col in range(start_col, end_col):
                wx = col * cell
                screen_x = wx - cam_x
                rw = min(cell, world.width - wx)
                density = ml.mana_density[row][col]
                color = self._mana_density_to_color(density, cap)
                rect = pygame.Rect(screen_x, screen_y, rw, rh)
                visible = rect.clip(screen_rect)
                if visible.width > 0 and visible.height > 0:
                    pygame.draw.rect(self.screen, color, visible)

    def invalidate_biome_cache(self) -> None:
        """ワールドリセット時に呼ぶ（GameApp.reset_simulation から）。"""
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None
