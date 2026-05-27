# input_handler.py
import pygame

from src.config import config
from src.utils.creature_helpers import distance_to_point


class InputHandler:
    """入力処理をまとめたクラス"""

    def __init__(self, engine):
        self.engine = engine

    def handle_events(self) -> bool:
        """全イベントを処理（メインループから呼ばれる）"""
        for event in pygame.event.get():
            if not self._process_event(event):
                return False
        return True

    def _process_event(self, event) -> bool:
        """1イベントずつ処理"""

        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.VIDEORESIZE:
            self.engine.resize_display(event.w, event.h)

        # カメラドラッグ操作
        self.engine.camera.handle_event(event)

        # 右クリック選択
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._handle_right_click(event)

        # キー入力
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)

        return True

    def _handle_right_click(self, event):
        """右クリックで生物または巣を選択"""
        wx = event.pos[0] + self.engine.camera.x
        wy = event.pos[1] + self.engine.camera.y
        self.engine.selected_creature = None
        self.engine.selected_nest = None

        for c in self.engine.world.creatures:
            dist = distance_to_point(c, wx, wy)
            if dist < c.traits.get("base_size", 10) + 25:
                self.engine.selected_creature = c
                return

        nest_system = getattr(self.engine.world, "nest_system", None)
        if nest_system is not None:
            nest = nest_system.find_nest_at(wx, wy)
            if nest is not None:
                self.engine.selected_nest = nest

    def _handle_keydown(self, event):
        """キー操作"""
        if event.key == pygame.K_r:
            self.engine.reset_simulation()
        elif event.key == pygame.K_SPACE:
            self.engine.paused = not self.engine.paused
        elif event.key == pygame.K_a:
            c = self.engine.creature_factory.create("Amoeba", world=self.engine.world)
            self.engine.world.add_creature(c)
        elif event.key == pygame.K_s:
            c = self.engine.creature_factory.create("Spider", world=self.engine.world)
            self.engine.world.add_creature(c)
        elif event.key == pygame.K_p:
            world = self.engine.world
            colony_cfg = (config.get_species("Ant") or {}).get("colony", {})
            if colony_cfg.get("enabled"):
                x, y = world.nest_system.spawn_position("Ant", colony_cfg)
                c = self.engine.creature_factory.create(
                    "Ant", world=world, x=x, y=y
                )
            else:
                c = self.engine.creature_factory.create("Ant", world=world)
            world.add_creature(c)
        elif event.key == pygame.K_h:
            self._add_nest_hole_at_cursor()
        elif event.key == pygame.K_d:
            self.engine.show_debug = not getattr(self.engine, 'show_debug', False)
        elif event.key == pygame.K_m:
            mode = getattr(self.engine, "map_view_mode", "biome")
            self.engine.map_view_mode = "mana" if mode == "biome" else "biome"
        elif event.key == pygame.K_ESCAPE:
            return False

    def _add_nest_hole_at_cursor(self) -> None:
        """マウス位置に巣穴を追加（選択中の巣、なければカーソル付近の巣）。"""
        world = self.engine.world
        nest_system = getattr(world, "nest_system", None)
        if nest_system is None:
            return

        mx, my = pygame.mouse.get_pos()
        wx = mx + self.engine.camera.x
        wy = my + self.engine.camera.y

        nest = self.engine.selected_nest
        if nest is None:
            nest = nest_system.find_nest_at(wx, wy, pick_radius=80.0)
        if nest is None:
            return

        nest_system.add_hole(nest, wx, wy)
        self.engine.selected_nest = nest
