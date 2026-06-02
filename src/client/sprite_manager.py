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
            self.base_path = Path(__file__).resolve().parents[2] / "pygame_ui" / "assets" / "sprites"
        else:
            self.base_path = Path(base_path)

        self._sprites: dict[str, pygame.Surface] = {}
        self._animations: dict[str, list[pygame.Surface]] = {}  # for animated sprite sheets, key -> list of frames
        self._scaled_cache: dict[tuple[str, int], pygame.Surface] = {}  # (key, target_diameter) -> scaled unrotated
        self._rotated_cache: dict[tuple[str, int], pygame.Surface] = {}  # (stable_key, quantized_angle) -> surf
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

        # 自動でよくあるアニメーションシートを検出してロード（walk, carry など）
        self._auto_load_common_animations()

        print(f"[SpriteManager] Loaded/Generated {len(self._sprites)} sprites from {self.base_path}")

    def load_sprite_sheet(self, key: str, sheet_path: str, num_frames: int, *, frame_width: Optional[int] = None):
        """スプライトシートをロードしてアニメーションとして登録。
        ユーザーの作り方:
          - creatures/red_ant_walk.png を横長シートで作成（例: 6フレーム、全体 192x32 px → 各フレーム 32x32）
          - シートを置くだけで load_all 時や初回 get 時に自動検出・ロードされる（_auto_load + lazy load）
          - または手動: mgr.load_sprite_sheet("creatures/red_ant_walk", "creatures/red_ant_walk.png", 6)

        対応状態（get_for_creature が自動選択）:
          walk: 移動中
          carry: 何か運んでいる時
          （idle はまだ walk fallback）
        """
        path = Path(sheet_path)
        if not path.is_absolute():
            path = self.base_path / sheet_path

        if not path.exists():
            print(f"[SpriteManager] Sprite sheet not found: {path}")
            return

        try:
            sheet = pygame.image.load(str(path)).convert_alpha()
            sw, sh = sheet.get_size()
            if frame_width is None:
                frame_width = sw // num_frames if num_frames > 0 else sw
            frames = []
            for i in range(num_frames):
                frame = sheet.subsurface(pygame.Rect(i * frame_width, 0, frame_width, sh)).copy()
                frames.append(frame)
            self._animations[key] = frames
            print(f"[SpriteManager] Loaded animated sheet '{key}' with {num_frames} frames")
        except Exception as e:
            print(f"[SpriteManager] Failed to load sheet {path}: {e}")

    def get_animated_frame(self, key: str, time_ms: int, fps: float = 8.0, *, fallback_size: int = 24) -> pygame.Surface:
        """アニメーションフレームを取得。時間ベース。
        time_ms: pygame.time.get_ticks() など。
        fps: 1秒あたりのフレーム数。
        シートがなければ通常の static sprite を返す。
        シートファイルが存在すれば自動ロードを試みる。
        """
        if key not in self._animations:
            # 自動ロード試行
            sheet_path = self.base_path / (key + ".png")
            if sheet_path.exists():
                # デフォルトフレーム数でロード（後で正確な数で上書き可）
                self.load_sprite_sheet(key, str(sheet_path), 6)

        if key in self._animations and self._animations[key]:
            frames = self._animations[key]
            frame_count = len(frames)
            frame_index = int((time_ms / 1000.0 * fps) % frame_count)
            return frames[frame_index]

        # アニメなし → 通常スプライトを返す（後方互換）
        return self.get(key, fallback_size=fallback_size)

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

    def get_scaled(self, key: str, target_diameter: int) -> pygame.Surface:
        """指定直径 (target_diameter x target_diameter) にスケールしたバージョンをキャッシュして返す。"""
        cache_key = (key, target_diameter)
        if cache_key in self._scaled_cache:
            return self._scaled_cache[cache_key]

        base = self.get(key)
        if base.get_width() == target_diameter and base.get_height() == target_diameter:
            self._scaled_cache[cache_key] = base
            return base

        scaled = pygame.transform.smoothscale(base, (target_diameter, target_diameter))
        self._scaled_cache[cache_key] = scaled
        return scaled

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

    def get_rotated(self, surface: pygame.Surface, angle_degrees: float, stable_key: Optional[str] = None) -> pygame.Surface:
        """回転したバージョンを返す（量子化 + キャッシュ）。
        stable_key を渡すと id(surface) ではなくそれを使ってキャッシュする（推奨）。
        これにより毎フレーム新しいscaled surfaceが来てもキャッシュが効く。
        """
        if surface is None:
            return surface

        step = self.rotation_step
        quantized = int(round(angle_degrees / step) * step) % 360

        if stable_key is not None:
            cache_key = (stable_key, quantized)
        else:
            cache_key = (id(surface), quantized)

        if cache_key in self._rotated_cache:
            return self._rotated_cache[cache_key]

        rotated = pygame.transform.rotate(surface, -quantized)
        self._rotated_cache[cache_key] = rotated
        return rotated

    def get_for_creature(
        self,
        species_name: str,
        size: float,
        *,
        carrying: bool = False,
        color_override: Optional[tuple[int, int, int]] = None,
        animation_time_ms: Optional[int] = None,
        walk_fps: float = 10.0,
    ) -> pygame.Surface:
        """クリーチャー向けの便利ゲッター。アニメーション対応。
        animation_time_ms を渡すと walk / carry アニメーションを試みる。
        対応シート例:
          creatures/red_ant_walk.png (6フレーム横並びシート)
          creatures/red_ant_carry.png (静止 or アニメ)
        """
        display_diam = max(4, int(size * 2))

        # アニメーション状態決定（Client側で velocity などから推定可能）
        state = "walk" if animation_time_ms is not None else None
        if carrying:
            state = "carry"

        base_key = f"creatures/{species_name}"
        anim_key = None
        if state:
            candidate = f"{base_key}_{state}"
            if candidate in self._animations or (self.base_path / f"{candidate}.png").exists():
                anim_key = candidate

        if anim_key and animation_time_ms is not None:
            # アニメーションフレーム取得（シートがあれば）
            frame = self.get_animated_frame(anim_key, animation_time_ms, fps=walk_fps, fallback_size=display_diam)
            # スケール
            if frame.get_width() != display_diam or frame.get_height() != display_diam:
                frame = pygame.transform.smoothscale(frame, (display_diam, display_diam))
            if color_override:
                frame = self.tint(frame, color_override)
            return frame

        # 通常（静止画 or プレースホルダ）
        if carrying:
            carry_key = f"creatures/{species_name}_carry"
            if carry_key in self._sprites:
                base_key = carry_key

        scaled_key = base_key if base_key in self._sprites else f"creatures/{species_name}"
        scaled = self.get_scaled(scaled_key, display_diam)

        if color_override:
            scaled = self.tint(scaled, color_override)

        return scaled

    def clear_caches(self) -> None:
        """回転キャッシュなどをクリア（リサイズ時など）。"""
        self._rotated_cache.clear()

    @property
    def has_sprites(self) -> bool:
        """本物の画像またはプレースホルダがロード/生成されているか。"""
        return bool(self._sprites)

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
            ("creatures/invader_ant", (40, 90, 180)),
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

    def _auto_load_common_animations(self):
        """load_all 後に、よくあるアニメ状態のシートを自動検出してロード。
        ユーザーが creatures/red_ant_walk.png などのシートを置いておけば自動で使われる。
        フレーム数は横幅から簡易推定（最低4）。
        静的な _carry.png などはシートとして扱わずスキップ（w <= h*2 くらいならシートとみなさない）。
        """
        common_states = ["walk", "carry", "idle", "attack"]
        for category in ["creatures"]:
            cat_dir = self.base_path / category
            if not cat_dir.exists():
                continue
            for png in sorted(cat_dir.glob("*_*.png")):
                stem = png.stem
                if "_" not in stem:
                    continue
                parts = stem.split("_")
                state = parts[-1]
                if state not in common_states:
                    continue
                key = f"{category}/{stem}"
                if key in self._animations:
                    continue
                try:
                    sheet = pygame.image.load(str(png))
                    w, h = sheet.get_size()
                    # シートらしい幅広のものだけシートとして扱う (e.g. 幅が縦の2倍以上)
                    if w <= h * 2:
                        continue  # 静的画像の可能性が高いのでスキップ
                    num_frames = max(4, min(12, w // max(h, 8)))
                    self.load_sprite_sheet(key, str(png), num_frames)
                except Exception:
                    pass


# グローバルシングルトン的な使い方（必要なら）
_default_manager: Optional[SpriteManager] = None

def get_default_sprite_manager() -> SpriteManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SpriteManager()
        _default_manager.load_all()
    return _default_manager
