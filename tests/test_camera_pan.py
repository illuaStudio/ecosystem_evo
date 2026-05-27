import unittest
from unittest.mock import MagicMock

from src.core.camera import Camera


class TestCameraPanInsets(unittest.TestCase):
    def setUp(self):
        self.camera = Camera()
        self.camera.screen_w = 1000
        self.camera.screen_h = 800
        world = MagicMock()
        world.width = 2000
        world.height = 1600
        self.camera.world = world

    def test_allows_pan_past_top_left_for_hud(self):
        self.camera.set_pan_insets(top=120, left=520, right=0, bottom=0)
        self.camera.x = -600
        self.camera.y = -200
        self.camera._clamp_position()
        self.assertEqual(self.camera.x, -520)
        self.assertEqual(self.camera.y, -120)

    def test_allows_pan_past_bottom_right(self):
        self.camera.set_pan_insets(top=0, left=0, right=100, bottom=80)
        self.camera.x = 1100
        self.camera.y = 880
        self.camera._clamp_position()
        self.assertEqual(self.camera.x, 1100)
        self.assertEqual(self.camera.y, 880)


if __name__ == "__main__":
    unittest.main()
