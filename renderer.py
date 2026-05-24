# renderer.py
import pygame

from config import config
from creature_helpers import format_life_stage_line


class Renderer:
    """描画専用クラス"""

    # ワールド外・余白（画面 > マップ時）と HUD 背面
    UI_MARGIN_COLOR = (14, 22, 14)
    UI_PANEL_COLOR = (0, 0, 0, 170)

    def __init__(self, screen, font, small_font, big_font):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.big_font = big_font
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None

    def draw(self, creatures, camera, selected_creature, paused, show_debug=False):
        # 毎フレーム必ず全画面クリア（未描画領域に UI が残るのを防ぐ）
        self.screen.fill(self.UI_MARGIN_COLOR)

        world = getattr(camera, "world", None)
        self._draw_background(world, camera)

        for c in creatures:
            if hasattr(c, "draw"):
                c.draw(self.screen, camera)

        self._draw_hud_panels(has_selection=selected_creature is not None, show_debug=show_debug)

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
                f"満腹度: {sc.satiety:.1f}/{sc.max_satiety:.0f}",
                f"サイズ: {sc.get_current_size():.1f} / {sc.traits.get('max_size', sc.get_current_size()):.1f}",
                f"年齢: {sc.age}",
                f"速度: {sc.get_current_speed():.2f}",
                f"現在のAction: {action_name}",
            ]
            life_line = format_life_stage_line(sc)
            if life_line:
                texts.insert(4, life_line)
            if not sc.alive:
                texts.insert(
                    3,
                    f"バイオマス: {sc.remaining_biomass:.1f}/{sc.initial_biomass:.1f} "
                    f"({sc.biomass_ratio() * 100:.0f}%)",
                )
            if world and sc.alive:
                biome = world.get_biome_at(sc.pos[0], sc.pos[1])
                texts.append(
                    f"バイオーム: {biome.get('display_name', biome.get('name', '?'))}"
                )

            for text in texts:
                self.screen.blit(self.small_font.render(text, True, (255, 255, 255)), (15, y))
                y += 24

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
            mana_label = f"    Mana: {w.mana:.0f}/{w.max_mana:.0f}  (回復×{mult:.2f})"
        self.screen.blit(
            self.font.render(f"生き物: {len(creatures):3d} 匹{mana_label}", True, (230, 245, 210)),
            (15, 55),
        )

        self.screen.blit(
            self.small_font.render(
                "Space:停止/再開  R:リセット  A:アメーバ追加  P:捕食者追加  右クリック:選択",
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
        top_h = 118 if not show_debug else 138
        pygame.draw.rect(panel, self.UI_PANEL_COLOR, (0, 0, sw, top_h))

        if has_selection:
            pygame.draw.rect(panel, self.UI_PANEL_COLOR, (0, 118, min(520, sw), sh - 118))

        self.screen.blit(panel, (0, 0))

    def _draw_background(self, world, camera) -> None:
        if world is None:
            return

        if world.biome_color_grid:
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

    def invalidate_biome_cache(self) -> None:
        """ワールドリセット時に呼ぶ（SimulationEngine.reset_simulation から）。"""
        self._biome_surface = None
        self._biome_surface_world_id = None
        self._ui_panel = None
