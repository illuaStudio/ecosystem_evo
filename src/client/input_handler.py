# input_handler.py
import pygame

from src.game import client_api
from src.sim.utils.creature_helpers import distance_to_point


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

        # 表示パネル左クリック（カメラドラッグより先）
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._handle_visibility_panel_click(event):
                return True

        # カメラドラッグ操作
        self.engine.camera.handle_event(event)

        # 右クリック選択
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._handle_right_click(event)

        # マウスホイールはカメラが処理（ズーム）
        # camera.handle_event(event) はすでに上の方で呼ばれているので、ここでは追加不要

        # キー入力
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)

        return True

    def _handle_visibility_panel_click(self, event) -> bool:
        vis = getattr(self.engine, "species_visibility", None)
        if vis is None:
            return False
        group_id = vis.hit_test_toggle(event.pos[0], event.pos[1])
        if group_id is None:
            return False
        vis.toggle_group(group_id)
        self.engine.clear_selection_if_creature_hidden()
        return True

    def _handle_right_click(self, event):
        """右クリックで生物または巣を選択（非表示の種は対象外）"""
        # ズーム対応：screen_to_world を使う
        wx, wy = self.engine.camera.screen_to_world(event.pos[0], event.pos[1])
        self.engine.selected_creature = None
        self.engine.selected_affiliation_id = None

        from src.sim.shelter.state import is_creature_sheltered

        vis = getattr(self.engine, "species_visibility", None)
        best = None
        best_dist = float("inf")
        for c in self.engine.world.creatures:
            if is_creature_sheltered(c) and not getattr(
                self.engine, "show_sheltered", False
            ):
                continue
            if vis is not None and not vis.is_creature_visible(c):
                continue
            dist = distance_to_point(c, wx, wy)
            pick_r = c.traits.get("base_size", 10) + 25
            if dist < pick_r and dist < best_dist:
                best_dist = dist
                best = c
        if best is not None:
            self.engine.selected_creature = best
            return

        nest_system = client_api.try_get_colony_orchestrator(self.engine.world)
        if nest_system is not None:
            affiliation_id = nest_system.find_affiliation_at(wx, wy)
            if affiliation_id is not None:
                self.engine.selected_affiliation_id = affiliation_id

    def _handle_keydown(self, event):
        """キー操作"""
        if event.key == pygame.K_r:
            self.engine.reset_simulation()
        elif event.key == pygame.K_SPACE:
            self.engine.paused = not self.engine.paused
        elif event.key == pygame.K_a:
            self.engine.debug_spawn_creature("springtail")
        elif event.key == pygame.K_s:
            self.engine.debug_spawn_creature("Spider")
        elif event.key == pygame.K_p:
            self.engine.debug_spawn_affiliation_member("red_ant")
        elif event.key == pygame.K_h:
            self._add_affiliation_access_at_cursor()
        elif event.key == pygame.K_d:
            self.engine.show_debug = not getattr(self.engine, 'show_debug', False)
        elif event.key == pygame.K_t:
            self.engine.show_territory = not getattr(
                self.engine, "show_territory", False
            )
        elif event.key == pygame.K_i:
            self.engine.show_sheltered = not getattr(
                self.engine, "show_sheltered", False
            )
        elif event.unicode in ('-', '－') or event.key == pygame.K_MINUS:
            self._adjust_simulation_speed(0.5)
        elif event.unicode in ('+', '=', '＋', '＝') or event.key in (pygame.K_EQUALS, pygame.K_PLUS):
            self._adjust_simulation_speed(2.0)
        elif event.key == pygame.K_0 or event.unicode == '0':
            # 速度リセット
            if getattr(self.engine, "sim_runner", None) is not None:
                client_api.set_simulation_speed(self.engine.sim_runner, 1.0)
                self.engine.notify("シミュ速度: x1.0 (reset)", source="client")
        elif getattr(self.engine, "species_visibility", None) is not None:
            if self.engine.species_visibility.toggle_group_by_hotkey(event.key):
                self.engine.clear_selection_if_creature_hidden()
        elif event.key == pygame.K_ESCAPE:
            return False

    def _add_affiliation_access_at_cursor(self) -> None:
        """マウス位置に colony_access を追加（選択中の巣、なければカーソル付近の巣）。"""
        world = self.engine.world
        nest_system = client_api.try_get_colony_orchestrator(world)
        if nest_system is None:
            return

        mx, my = pygame.mouse.get_pos()
        wx, wy = self.engine.camera.screen_to_world(mx, my)

        affiliation_id = self.engine.selected_affiliation_id
        if affiliation_id is None:
            affiliation_id = nest_system.find_affiliation_at(wx, wy, pick_radius=80.0)
        if affiliation_id is None:
            return

        _ok, msg = nest_system.try_place_hole(affiliation_id, wx, wy)
        self.engine.notify(msg, source="game")
        self.engine.selected_affiliation_id = affiliation_id

    def _adjust_simulation_speed(self, factor: float) -> None:
        """シミュレーション速度を factor 倍して設定（Game層の client_api 経由）。"""
        if getattr(self.engine, "sim_runner", None) is None:
            return
        try:
            current = client_api.get_simulation_speed(self.engine.sim_runner)
            new_speed = current * float(factor)
            applied = client_api.set_simulation_speed(self.engine.sim_runner, new_speed)
            self.engine.notify(f"シミュ速度: x{applied:.1f}", source="client")
        except Exception:
            pass
