# camera.py
import pygame

from src.config import config


class Camera:
    """カメラ（視点）管理クラス"""

    def __init__(self):
        # 初期画面サイズ
        self.screen_w = config.game["camera_width"]
        self.screen_h = config.game["camera_height"]

        self.world = None
        self.x = 0
        self.y = 0
        self.dragging = False
        self.last_pos = (0, 0)

    def set_world(self, world):
        """Worldを設定（engineから呼ばれる）"""
        self.world = world
        self.center()

    def _clamp_axis(self, pos: float, world_size: int, screen_size: int) -> float:
        """ワールドが画面より小さいときも余白内でパンできるようクランプする。"""
        low = min(0, world_size - screen_size)
        high = max(0, world_size - screen_size)
        return max(low, min(high, pos))

    def _clamp_position(self) -> None:
        if not self.world:
            return
        self.x = self._clamp_axis(self.x, self.world.width, self.screen_w)
        self.y = self._clamp_axis(self.y, self.world.height, self.screen_h)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = True
            self.last_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.last_pos[0]
            dy = event.pos[1] - self.last_pos[1]
            self.x -= dx
            self.y -= dy
            self.last_pos = event.pos
            self._clamp_position()

    def center(self):
        """ワールドを画面中央に配置（ワールドが画面より小さくても中央になる）。"""
        if self.world:
            self.x = (self.world.width - self.screen_w) / 2
            self.y = (self.world.height - self.screen_h) / 2
            self._clamp_position()

    def set_screen_size(self, width: int, height: int) -> None:
        """表示領域の変更後にカメラ境界を再計算する。"""
        self.screen_w = width
        self.screen_h = height
        self._clamp_position()
