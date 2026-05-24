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

            # 境界制限
            if self.world:
                self.x = max(0, min(self.world.width - self.screen_w, self.x))
                self.y = max(0, min(self.world.height - self.screen_h, self.y))

    def center(self):
        """画面を中央に配置"""
        if self.world:
            self.x = (self.world.width - self.screen_w) // 2
            self.y = (self.world.height - self.screen_h) // 2
