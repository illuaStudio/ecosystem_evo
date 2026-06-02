# camera.py
import pygame

from src.config import config


class Camera:
    """カメラ（視点）管理クラス。パン + ズーム対応。"""

    def __init__(self):
        # 初期画面サイズ
        self.screen_w = config.client["camera_width"]
        self.screen_h = config.client["camera_height"]

        self.world = None
        self.x = 0
        self.y = 0
        self.dragging = False
        self.last_pos = (0, 0)

        # ズーム
        self.zoom = 1.0
        self.min_zoom = 0.05
        self.max_zoom = 20.0
        self.zoom_factor = 1.2  # ホイール1回あたりの倍率

        # HUD に隠れないよう、マップ端より先までパンできる余白（ピクセル）
        self._pan_inset_top = 0.0
        self._pan_inset_left = 0.0
        self._pan_inset_right = 0.0
        self._pan_inset_bottom = 0.0

    def set_world(self, world, *, center: bool = True) -> None:
        """Worldを設定。center=False なら現在のパン位置を維持する。"""
        self.world = world
        if center:
            self.center()
        else:
            self._clamp_position()

    def set_pan_insets(
        self,
        *,
        top: float = 0,
        left: float = 0,
        right: float = 0,
        bottom: float = 0,
    ) -> None:
        """UI オーバーレイ分だけマップ端を超えてドラッグできる範囲を設定する。"""
        changed = (
            self._pan_inset_top != top
            or self._pan_inset_left != left
            or self._pan_inset_right != right
            or self._pan_inset_bottom != bottom
        )
        self._pan_inset_top = top
        self._pan_inset_left = left
        self._pan_inset_right = right
        self._pan_inset_bottom = bottom
        if changed:
            self._clamp_position()

    def _clamp_axis(
        self,
        pos: float,
        world_size: int,
        screen_size: int,
        *,
        inset_before: float,
        inset_after: float,
    ) -> float:
        """ワールドが画面より小さいときも余白内でパンできるようクランプする。

        inset_before: マップ先端（左上）を UI の下へずらすための余白
        inset_after: マップ末端（右下）を UI から離すための余白
        """
        base_low = min(0, world_size - screen_size)
        base_high = max(0, world_size - screen_size)
        low = base_low - inset_before
        high = base_high + inset_after
        return max(low, min(high, pos))

    def _clamp_position(self) -> None:
        if not self.world:
            return
        # ズーム考慮: 画面がカバーするワールド幅 = screen / zoom
        eff_w = self.screen_w / self.zoom
        eff_h = self.screen_h / self.zoom
        self.x = self._clamp_axis(
            self.x,
            self.world.width,
            eff_w,
            inset_before=self._pan_inset_left,
            inset_after=self._pan_inset_right,
        )
        self.y = self._clamp_axis(
            self.y,
            self.world.height,
            eff_h,
            inset_before=self._pan_inset_top,
            inset_after=self._pan_inset_bottom,
        )

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = True
            self.last_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.last_pos[0]
            dy = event.pos[1] - self.last_pos[1]
            # ズーム中はドラッグ量を世界単位に変換
            self.x -= dx / self.zoom
            self.y -= dy / self.zoom
            self.last_pos = event.pos
            self._clamp_position()
        elif event.type == pygame.MOUSEWHEEL:
            # ズーム（カーソル位置を中心に）
            mx, my = pygame.mouse.get_pos()
            factor = self.zoom_factor if event.y > 0 else 1.0 / self.zoom_factor
            self.zoom_at(mx, my, factor)

    def center(self):
        """ワールドを画面中央に配置（ワールドが画面より小さくても中央になる）。"""
        if self.world:
            eff_w = self.screen_w / self.zoom
            eff_h = self.screen_h / self.zoom
            self.x = (self.world.width - eff_w) / 2
            self.y = (self.world.height - eff_h) / 2
            self._clamp_position()

    def set_screen_size(self, width: int, height: int) -> None:
        """表示領域の変更後にカメラ境界を再計算する。"""
        self.screen_w = width
        self.screen_h = height
        self._clamp_position()

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        """ワールド座標を画面座標に変換（ズーム適用）。"""
        return int((wx - self.x) * self.zoom), int((wy - self.y) * self.zoom)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """画面座標をワールド座標に変換（ズーム適用）。"""
        return self.x + sx / self.zoom, self.y + sy / self.zoom

    def zoom_at(self, screen_x: int, screen_y: int, factor: float) -> None:
        """指定画面位置を中心にズーム（factor >1 で拡大）。"""
        wx, wy = self.screen_to_world(screen_x, screen_y)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        self.x = wx - screen_x / self.zoom
        self.y = wy - screen_y / self.zoom
        self._clamp_position()
