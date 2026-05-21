# renderer.py
import pygame
from config import config
from creature_helpers import format_life_stage_line


class Renderer:
    """描画専用クラス"""
    
    def __init__(self, screen, font, small_font, big_font):
        self.screen = screen
        self.font = font
        self.small_font = small_font
        self.big_font = big_font

    def draw(self, creatures, camera, selected_creature, paused, show_debug=False):
        # Worldの背景色を使用（stageは削除済み）
        if hasattr(camera, 'world') and camera.world:
            bg_color = camera.world.background_color
        else:
            bg_color = config.game.get("background_color", [20, 40, 25])  # フォールバック
        
        self.screen.fill(bg_color)

        # 生物描画
        for c in creatures:
            if hasattr(c, 'draw'):
                c.draw(self.screen, camera)

        # 選択情報
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
            # 右クリック選択時: ライフステージ（life_cycle がある種）
            life_line = format_life_stage_line(sc)
            if life_line:
                texts.insert(4, life_line)
            if not sc.alive:
                texts.insert(
                    3,
                    f"バイオマス: {sc.remaining_biomass:.1f}/{sc.initial_biomass:.1f} "
                    f"({sc.biomass_ratio() * 100:.0f}%)",
                )

            for text in texts:
                self.screen.blit(self.small_font.render(text, True, (255, 255, 255)), (15, y))
                y += 24

        # UI
        status = "【PAUSED】" if paused else "実行中"
        self.screen.blit(self.big_font.render(
            f"{config.game['game_title']} v{config.game['version']}   {status}", 
            True, (200, 255, 200)), (15, 10))
        
        mana_label = ""
        if hasattr(camera, "world") and camera.world:
            w = camera.world
            mana_label = f"    Mana: {w.mana:.0f}/{w.max_mana:.0f}"
        self.screen.blit(self.font.render(
            f"生き物: {len(creatures):3d} 匹{mana_label}",
            True, (230, 245, 210)), (15, 55))
        
        self.screen.blit(self.small_font.render(
            "Space:停止/再開  R:リセット  A:アメーバ追加  P:捕食者追加  右クリック:選択", 
            True, (160, 200, 255)), (15, 85))

        if show_debug:
            debug_text = self.small_font.render(
                f"Debug Mode | 生物: {len(creatures)}",
                True,
                (255, 255, 100),
            )
            self.screen.blit(debug_text, (15, 110))