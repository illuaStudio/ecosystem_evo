"""Client層用 スプライト/画像アセット管理（Game層非依存）。

目的:
- 現在シェイプで描画している生物・巣などを画像に置き換えるための基盤。
- 大量表示時のパフォーマンスを考慮したキャッシュ（回転・スケール）。
- 将来的にGPUバックエンド（moderngl等）に置き換えやすい抽象化。

使用例（Clientレンダラー側）:
    manager = SpriteManager()
    manager.load_all()
    sprite = manager.get("red_ant", state="default")
    tinted = manager.tint(sprite, creature.species.color)
    rotated = manager.get_rotated(tinted, angle_degrees)
    screen.blit(rotated, (sx - w//2, sy - h//2))
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import pygame


class SpriteManager:
    """画像スプライトのロード・取得・変換を担当するClient専用クラス。

    現在はPNG前提。将来的にスプライトシートやアニメーション対応。
    """

    def __init__(self, base_path: Optional[Path] = None):
        # デフォルトは pygame_ui/assets/sprites/
        if base_path is None:
            # プロジェクトルートからの相対
            self.base_path = Path(__file__).resolve().parents[3] / "pygame_ui" / "assets" / "sprites"
        else:
            self.base_path = Path(base_path)

        self._sprites: dict[str, pygame.Surface] = {}
        self._rotated_cache: dict[tuple[str, int], pygame.Surface] = {}  # (key, quantized_angle) -> surf
        self._loaded = False

        # 回転量子化（度）。小さいほど高品質だがメモリ増。
        self.rotation_step = 8

    def load_all(self) -> None:
        """起動時に全スプライトをロード。見つからない場合はプレースホルダ生成。"""
        if self._loaded:
            return

        categories = ["creatures", "nests", "obstacles", "items"]
        for category in categories:
            cat_dir = self.base_path / category
            if not cat_dir.exists():
                continue
            for png in cat_dir.glob("*.png"):
                key = f"{category}/{png.stem}"
                try:
                    surf = pygame.image.load(str(png)).convert_alpha()
                    self._sprites[key] = surf
                except Exception as e:
                    print(f"[SpriteManager] Failed to load {png}: {e}")

        self._loaded = True

        # 画像が全くない場合、主要な種に対して自動でプレースホルダ画像を生成
        # これにより「画像モード」に即切り替え可能（本物のPNGを置けば上書きされる）
        self._ensure_placeholders_for_known_species()

        print(f"[SpriteManager] Loaded/Generated {len(self._sprites)} sprites from {self.base_path}")

    def _get_placeholder(self, key: str, size: int = 24, color: tuple[int, int, int] = (200, 100, 100)) -> pygame.Surface:
        """画像が見つからない場合のフォールバック（円形シェイプ）。"""
        surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (size, size), size)
        pygame.draw.circle(surf, (255, 255, 255), (size, size), size, 2)
        # キー名を小さく描画
        try:
            font = pygame.font.SysFont("msgothic", max(8, size // 2))
            text = font.render(key.split("/")[-1][:6], True, (0, 0, 0))
            surf.blit(text, (size - text.get_width() // 2, size - text.get_height() // 2))
        except Exception:
            pass
        return surf

    def get(self, key: str, *, fallback_size: int = 24) -> pygame.Surface:
        """キー（例: "creatures/red_ant"）でスプライトを取得。
        存在しなければプレースホルダを返す。
        """
        if not self._loaded:
            self.load_all()

        if key in self._sprites:
            return self._sprites[key]

        # フォールバック
        return self._get_placeholder(key, size=fallback_size)

    def get_scaled(self, key: str, target_size: int) -> pygame.Surface:
        """指定サイズにスケールしたバージョンを返す（キャッシュは簡易版）。"""
        base = self.get(key)
        if base.get_width() == target_size * 2 and base.get_height() == target_size * 2:
            return base
        # シンプルに毎回スケール（後でキャッシュ強化）
        return pygame.transform.smoothscale(base, (target_size * 2, target_size * 2))

    def tint(self, surface: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
        """指定色でティント（乗算風）。元のアルファを保持。"""
        if surface is None:
            return surface
        tinted = surface.copy()
        # 色を掛ける簡易方法（より正確にはBLEND_MULTだが、互換性のため）
        r, g, b = color
        # 明るさ調整付きの簡易ティント
        overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
        overlay.fill((r, g, b, 180))  # アルファで強さを調整
        tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    def get_rotated(self, surface: pygame.Surface, angle_degrees: float) -> pygame.Surface:
        """回転したバージョンを返す（量子化 + キャッシュ）。"""
        if surface is None:
            return surface

        # 量子化
        step = self.rotation_step
        quantized = int(round(angle_degrees / step) * step) % 360

        cache_key = (id(surface), quantized)  # 簡易。実際はキー文字列の方が良い
        if cache_key in self._rotated_cache:
            return self._rotated_cache[cache_key]

        rotated = pygame.transform.rotate(surface, -quantized)  # pygameは反時計回り
        self._rotated_cache[cache_key] = rotated
        return rotated

    def get_for_creature(
        self,
        species_name: str,
        size: float,
        *,
        carrying: bool = False,
        color_override: Optional[tuple[int, int, int]] = None,
    ) -> pygame.Surface:
        """クリーチャー向けの便利ゲッター。"""
        # 基本キー決定（後で拡張: _soldier など）
        base_key = f"creatures/{species_name}"
        if carrying:
            # 運搬中は別キー or 後でオーバーレイ
            base_key = f"creatures/{species_name}_carry"  # 存在しなければ通常にフォールバック

        sprite = self.get(base_key)
        if color_override:
            sprite = self.tint(sprite, color_override)

        scaled = self.get_scaled(base_key if base_key in self._sprites else f"creatures/{species_name}", int(size * 2))
        if color_override:
            scaled = self.tint(scaled, color_override)
        return scaled

    def clear_caches(self) -> None:
        """回転キャッシュなどをクリア（リサイズ時など）。"""
        self._rotated_cache.clear()

    def _ensure_placeholders_for_known_species(self) -> None:
        """画像ファイルが一切ない場合でも、主要クリーチャーのプレースホルダを生成して
        「画像blitモード」に即移行できるようにする。
        """
        if self._sprites:
            return  # すでに何か画像があれば生成しない

        known = [
            ("creatures/red_ant", (220, 60, 60)),
            ("creatures/red_ant_soldier", (180, 40, 40)),
            ("creatures/spider", (80, 80, 120)),
            ("creatures/rival_ant", (60, 120, 220)),
            ("creatures/rival_ant_soldier", (40, 90, 180)),
            ("nests/red_ant", (200, 80, 50)),
            ("obstacles/rock", (120, 120, 120)),
            ("items/biomass", (100, 140, 60)),
        ]

        for key, color in known:
            # 32x32 のシンプルな円形プレースホルダ
            size = 32
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (size // 2, size // 2), size // 2 - 2)
            pygame.draw.circle(surf, (255, 255, 255), (size // 2, size // 2), size // 2 - 2, 2)
            # ラベル
            try:
                font = pygame.font.SysFont("msgothic", 10)
                label = key.split("/")[-1][:5]
                txt = font.render(label, True, (0, 0, 0))
                surf.blit(txt, (size // 2 - txt.get_width() // 2, size // 2 - txt.get_height() // 2))
            except Exception:
                pass

            self._sprites[key] = surf


# グローバルシングルトン的な使い方（必要なら）
_default_manager: Optional[SpriteManager] = None

def get_default_sprite_manager() -> SpriteManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SpriteManager()
        _default_manager.load_all()
    return _default_manager
