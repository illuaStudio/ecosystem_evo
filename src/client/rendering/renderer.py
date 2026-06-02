# renderer.py
import math
import pygame

from src.game import client_api


def colony(world):
    """Client から Game の colony データにアクセスする際は必ず client_api 経由。
    異なるAI (Client担当 / Game担当) が並行開発できるための境界。
    """
    return client_api.try_get_colony_orchestrator(world)

from src.config import config
from src.client.rendering.zone_renderer import ZoneRenderer
from src.client.rendering.obstacle_renderer import ObstacleRenderer
from src.client.rendering.spawn_emitter_renderer import SpawnEmitterRenderer
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
    get_combat_target,
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
        selected_affiliation_id,
        paused,
        show_debug=False,
        map_view_mode="biome",
        show_territory=False,
        show_sheltered=False,
        user_message: str = "",
        message_feed=None,
        player_affiliation_id: str = "",
        game_state=None,
        species_visibility: SpeciesVisibilityManager | None = None,
        sim_time: float = 0.0,
        sim_speed: float = 1.0,
    ):
        self._show_territory_hud = show_territory
        self._show_sheltered_hud = show_sheltered
        # 毎フレーム必ず全画面クリア（未描画領域に UI が残るのを防ぐ）
        self.screen.fill(self.UI_MARGIN_COLOR)

        world = getattr(camera, "world", None)
        self._draw_background(world, camera, map_view_mode)

        if world is not None:
            affiliation_id = selected_affiliation_id
            NestRenderer.draw_territories(
                world,
                self.screen,
                camera,
                show_territory=show_territory,
                selected_affiliation_id=affiliation_id,
            )
            NestRenderer.draw(world, self.screen, camera, affiliation_id)
            ZoneRenderer.draw(world, self.screen, camera)
            ObstacleRenderer.draw(world, self.screen, camera)
            SpawnEmitterRenderer.draw(world, self.screen, camera)
            if show_territory and affiliation_id is not None:
                import pygame as _pg

                mx, my = _pg.mouse.get_pos()
                wx, wy = camera.screen_to_world(mx, my)
                NestRenderer.draw_affiliation_access_placement_preview(
                    world,
                    self.screen,
                    camera,
                    affiliation_id,
                    wx,
                    wy,
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

        wos = getattr(world, "world_object_system", None)
        if wos is not None and config.client.get("show_field_biomass", False):
            for obj in wos.iter_field_pickups():
                if obj.is_pickup_depleted():
                    continue
                sx, sy = camera.world_to_screen(obj.x, obj.y)
                ratio = obj.fill_ratio if obj.size_from_fill_ratio else 1.0
                ratio = max(0.0, min(1.0, ratio))
                base_r = 3 + math.sqrt(ratio) * 5
                radius = max(2, int(base_r * camera.zoom))
                pygame.draw.circle(self.screen, obj.color, (sx, sy), radius)
                pygame.draw.circle(self.screen, (40, 36, 32), (sx, sy), radius, max(1, int(camera.zoom)))

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

        has_selection = selected_creature is not None or selected_affiliation_id is not None
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
            if world and sc.alive:
                sx, sy = entity_xy(sc)
                biome = world.biome.get_biome_at(sx, sy)
                texts.append(
                    f"バイオーム: {biome.get('display_name', biome.get('name', '?'))}"
                )

            from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

            cid = get_creature_affiliation_id(sc)
            if cid and world is not None:
                root = colony(world).get_affiliation_root(cid)
                if root is not None and root.storage is not None:
                    texts.append(
                        f"コロニー {cid}: 食料 "
                        f"{root.storage.stored_mass:.0f}/{root.storage.capacity:.0f}"
                    )
                    texts.append(
                        f"  備蓄率 {colony(world).affiliation_fill_ratio(cid) * 100:.0f}%"
                    )
                    texts.append(
                        f"コロニー: {colony(world).total_member_count(cid)} 匹"
                    )
                    from src.sim.utils.territory_helpers import get_territory_radius_for_affiliation
                    from src.sim.utils.world_object_helpers import affiliation_access_count

                    access_n = affiliation_access_count(world, cid)
                    texts.append(
                        f"勢力 {cid} | テリトリー半径 "
                        f"{get_territory_radius_for_affiliation(world, cid):.0f} px | 接続点 {access_n}"
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

            combat_view = client_api.get_combat_target_view(sc)
            hunt_view = client_api.get_hunt_target_view(sc)
            if combat_view is not None:
                texts.append(f"戦闘対象: {combat_view.name}")
            elif hunt_view is not None:
                texts.append(f"狩り対象: {hunt_view.name}")
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

        elif selected_affiliation_id is not None and world is not None:
            y = self._draw_affiliation_detail_panel(selected_affiliation_id, world, y=130)

        status = "【PAUSED】" if paused else "実行中"
        self.screen.blit(
            self.big_font.render(
                f"{config.game_app['game_title']} v{config.game_app['version']}   {status}",
                True,
                (200, 255, 200),
            ),
            (15, 10),
        )

        # シミュレーション時間と加速倍率表示（Game層から提供された値）
        if world is not None:
            sim_str = f"SimTime: {sim_time:.1f}s   Speed: x{sim_speed:.1f}"
            self.screen.blit(
                self.small_font.render(sim_str, True, (180, 255, 180)),
                (15, 32),
            )

        hud_extra = ""
        if world:
            territory_on = getattr(self, "_show_territory_hud", False)
            sheltered_on = getattr(self, "_show_sheltered_hud", False)
            territory_label = "  テリトリー: ON" if territory_on else ""
            sheltered_label = "  巣内: ON" if sheltered_on else ""
            hud_extra = f"    表示: バイオーム{territory_label}{sheltered_label}"
        visible_count = len(creatures)
        if species_visibility is not None:
            visible_count = sum(
                1 for c in creatures if species_visibility.is_creature_visible(c)
            )
        count_label = f"表示: {visible_count:3d} / 全 {len(creatures):3d} 匹"
        self.screen.blit(
            self.font.render(f"{count_label}{hud_extra}", True, (230, 245, 210)),
            (15, 55),
        )

        if world is not None:
            self._draw_population_panel(world)
            if player_affiliation_id:
                self._draw_queen_status_panel(world, player_affiliation_id, game_state)
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
                "Space:停止/再開  R:リセット  T:テリトリー  I:巣内表示  1〜5:生態表示  -:減速  +:加速  0:速度1x  右クリ:個体/巣  右下:表示パネル",
                True,
                (160, 200, 255),
            ),
            (15, 85),
        )

        if show_debug and world:
            debug_text = self.small_font.render(
                f"Debug | 生物: {len(creatures)}",
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

    def _draw_queen_status_panel(self, world, player_affiliation_id: str, game_state) -> None:
        """右上（個体数パネル下）: プレイヤー女王の状態。"""
        from src.client.queen_status import build_queen_panel_lines

        lines = build_queen_panel_lines(world, player_affiliation_id, game_state)
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
            "micro_fauna": "1",
            "red_ant": "2",
            "spider": "3",
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

    def _target_view_visible_for_overlay(
        self, view: client_api.TargetView | None, species_visibility: SpeciesVisibilityManager | None
    ) -> bool:
        if view is None:
            return False
        if species_visibility is None:
            return True
        if not view.is_creature or view.species_name is None:
            return True
        return species_visibility.is_species_visible(view.species_name)

    def _creature_visible_for_overlay(
        self, creature, species_visibility: SpeciesVisibilityManager | None
    ) -> bool:
        """攻撃者リストなど、常に creature のオーバーレイ用。"""
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
        combat_view = client_api.get_combat_target_view(sc)
        hunt_view = client_api.get_hunt_target_view(sc)
        if combat_view is not None and self._target_view_visible_for_overlay(
            combat_view, species_visibility
        ):
            self._draw_hunt_link_to_view(sc, combat_view, camera, (120, 160, 255))
            self._draw_target_view_marker(combat_view, camera, (100, 140, 255))
        elif hunt_view is not None and self._target_view_visible_for_overlay(
            hunt_view, species_visibility
        ):
            self._draw_hunt_link_to_view(sc, hunt_view, camera, (255, 90, 90))
            self._draw_target_view_marker(hunt_view, camera, (255, 120, 80))

        attackers = find_attackers_for_target(world, sc)
        for attacker in attackers:
            if not self._creature_visible_for_overlay(attacker, species_visibility):
                continue
            link_color = (80, 120, 255) if get_combat_target(attacker) is sc else (255, 60, 60)
            self._draw_hunt_link(attacker, sc, camera, link_color)
            hx, hy = entity_xy(attacker)
            hsx, hsy = camera.world_to_screen(hx, hy)
            hsize = int(attacker.traits.get("base_size", 8))
            pygame.draw.circle(
                self.screen, (255, 100, 100), (hsx, hsy), max(2, int((hsize + 14) * camera.zoom)), max(1, int(2 * camera.zoom))
            )

    def _draw_hunt_link(
        self, predator, prey, camera, color: tuple[int, int, int]
    ) -> None:
        """クリーチャー同士のハントリンク描画（攻撃者→選択個体 など）。"""
        px, py = entity_xy(predator)
        tx, ty = entity_xy(prey)
        sx1, sy1 = camera.world_to_screen(px, py)
        sx2, sy2 = camera.world_to_screen(tx, ty)
        lw = max(1, int(2 * camera.zoom))
        pygame.draw.line(self.screen, color, (sx1, sy1), (sx2, sy2), lw)
        mid_x, mid_y = (sx1 + sx2) // 2, (sy1 + sy2) // 2
        pygame.draw.circle(self.screen, color, (mid_x, mid_y), max(2, int(4 * camera.zoom)))

    def _draw_hunt_link_to_view(
        self, predator, target_view: client_api.TargetView, camera, color: tuple[int, int, int]
    ) -> None:
        # TargetView has .x/.y so entity_xy works on it (falls back to getattr x,y)
        self._draw_hunt_link(predator, target_view, camera, color)

    def _draw_target_view_marker(
        self, target_view: client_api.TargetView, camera, color: tuple[int, int, int]
    ) -> None:
        sx, sy = camera.world_to_screen(target_view.x, target_view.y)
        size = int(target_view.size)
        r = max(2, int((size + 14) * camera.zoom))
        pygame.draw.circle(self.screen, color, (sx, sy), r, max(1, int(2 * camera.zoom)))
        pygame.draw.circle(self.screen, (255, 240, 180), (sx, sy), max(2, int((size + 18) * camera.zoom)), max(1, int(camera.zoom)))
        font_size = max(8, int(12 * camera.zoom))
        font = pygame.font.SysFont("msgothic", font_size)
        label = font.render("TARGET", True, (255, 220, 160))
        off = max(4, int(32 * camera.zoom))
        self.screen.blit(label, (sx - max(4, int(22 * camera.zoom)), sy - size * camera.zoom - off))

    def _draw_affiliation_detail_panel(self, affiliation_id: str, world, y: int = 130) -> int:
        """選択中のコロニー詳細 HUD。戻り値は次の描画 Y。"""
        from src.sim.utils.affiliation_config_helpers import (
            get_affiliation_profile,
            get_access_deposit_cost,
            get_max_access_points,
        )
        from src.sim.utils.world_object_helpers import (
            affiliation_access_count,
            affiliation_site_xy,
            affiliation_stored_mass,
            affiliation_capacity,
            get_affiliation_root,
            owner_species_for_affiliation,
        )

        ns = colony(world)
        total = ns.total_member_count(affiliation_id)
        root = get_affiliation_root(world, affiliation_id)

        leak_per_tick = float(
            get_affiliation_profile(world, affiliation_id).get("storage_leak_per_tick", 0)
        )

        self.screen.blit(
            self.font.render("【選択中のコロニー】", True, (255, 200, 120)), (15, y)
        )
        y += 35

        colony_world = getattr(world, "affiliation_settings", {}) or {}
        access_cost = get_access_deposit_cost(colony_world)
        max_access = get_max_access_points(colony_world)
        access_count = affiliation_access_count(world, affiliation_id)
        sx, sy = affiliation_site_xy(world, affiliation_id)
        owner = owner_species_for_affiliation(world, affiliation_id)
        stored = affiliation_stored_mass(world, affiliation_id)
        cap = affiliation_capacity(world, affiliation_id)
        ratio = ns.affiliation_fill_ratio(affiliation_id)

        texts = [
            f"勢力:{affiliation_id}  種:{owner}",
            f"位置: ({sx:.0f}, {sy:.0f})",
            f"接続点: {access_count}/{max_access}  (H:カーソルに設置 / 費用 {access_cost:.0f})",
            f"食料: {stored:.1f} / {cap:.0f}",
            f"備蓄率: {ratio * 100:.1f}%",
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

        if world.biome.biome_color_grid:
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
        """ワールド範囲だけ単色で塗る（マップが画面より小さいときの余白は残す、ズーム対応）。"""
        # ズーム時は visible world rect を計算してスケール描画相当に
        left, top = camera.screen_to_world(0, 0)
        right, bottom = camera.screen_to_world(self.screen.get_width(), self.screen.get_height())
        # ワールド矩形を画面にマップ
        wx1, wy1 = camera.world_to_screen(0, 0)
        wx2, wy2 = camera.world_to_screen(world.width, world.height)
        rect = pygame.Rect(min(wx1, wx2), min(wy1, wy2), abs(wx2 - wx1), abs(wy2 - wy1))
        visible = rect.clip(self.screen.get_rect())
        if visible.width > 0 and visible.height > 0:
            pygame.draw.rect(self.screen, color, visible)

    def _draw_biome_tiles(self, world, camera) -> None:
        self._ensure_biome_surface(world)
        # ズーム対応: 見えるワールド範囲を計算し、サブサーフェスをスケールして描画
        left, top = camera.screen_to_world(0, 0)
        right, bottom = camera.screen_to_world(self.screen.get_width(), self.screen.get_height())
        src = pygame.Rect(int(left), int(top), int(right - left), int(bottom - top))
        biome_rect = self._biome_surface.get_rect()
        src = src.clip(biome_rect)  # 確実に surface 内に収まる intersection を取る (clamp_ip だと oversized rect のサイズが残る問題を回避)
        if src.width <= 0 or src.height <= 0:
            return

        sub = self._biome_surface.subsurface(src).copy()
        if camera.zoom != 1.0:
            new_w = max(1, int(src.width * camera.zoom))
            new_h = max(1, int(src.height * camera.zoom))
            sub = pygame.transform.smoothscale(sub, (new_w, new_h))

        # 左上を正しい位置に (src は clip 後の intersection)
        dest_x, dest_y = camera.world_to_screen(src.x, src.y)
        self.screen.blit(sub, (dest_x, dest_y))

    def invalidate_biome_cache(self) -> None:
        """ワールドリセット時に呼ぶ（GameApp.reset_simulation から）。"""
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None
