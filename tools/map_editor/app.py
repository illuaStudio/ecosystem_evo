"""Pygame マップエディタ Phase 1。"""
from __future__ import annotations

import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from map_editor.model import WORLD_REL_PATH, WorldMapDocument
from src.client.camera import Camera
from src.client.rendering.obstacle_renderer import ObstacleRenderer
from src.client.rendering.renderer import Renderer
from src.client.rendering.spawn_emitter_renderer import SpawnEmitterRenderer
from src.client.rendering.zone_renderer import ZoneRenderer
from src.client.rendering.nest_renderer import get_faction_style

LAYER_ORDER = ["obstacle", "zone", "spawn", "colony_site"]
LAYER_LABELS = {
    "obstacle": "障害物",
    "zone": "Zone（毒霧等）",
    "spawn": "湧きエミッタ",
    "colony_site": "拠点（コロニー）",
    "nest": "拠点（コロニー）",
}
LAYER_KEYS = {
    pygame.K_1: "obstacle",
    pygame.K_2: "zone",
    pygame.K_3: "spawn",
    pygame.K_4: "colony_site",
}
SITE_LAYERS = frozenset({"nest", "colony_site"})
HUD_LEFT = 280
HUD_TOP = 88


class MapEditorApp:
    def __init__(self) -> None:
        pygame.init()
        self.screen_w = 1280
        self.screen_h = 800
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
        pygame.display.set_caption("Ecosystem Evo — マップエディタ")

        self.font = pygame.font.SysFont("msgothic", 20)
        self.small_font = pygame.font.SysFont("msgothic", 16)
        self.big_font = pygame.font.SysFont("msgothic", 28)

        self.renderer = Renderer(
            self.screen,
            self.font,
            self.small_font,
            self.big_font,
        )

        self.doc = WorldMapDocument.load()
        self.world = self.doc.rebuild_preview_world()
        self.camera = Camera()
        self.camera.set_screen_size(self.screen_w, self.screen_h)
        self.camera.set_pan_insets(top=HUD_TOP, left=HUD_LEFT)
        self.camera.set_world(self.world)

        self.active_layer = "obstacle"
        self.type_index = 0
        self.selected_uid: str | None = None
        self.status = "読み込み完了"
        self._panning = False
        self._pan_last = (0, 0)
        self._dragging_uid: str | None = None
        self._dirty = False
        self._space_held = False

    def _current_type(self) -> str:
        options = self.doc.type_options(self.active_layer)
        if not options:
            return "default"
        self.type_index %= len(options)
        return options[self.type_index]

    def _reload_world(self) -> None:
        self.doc._flush_objects()
        self.world = self.doc.rebuild_preview_world()
        self.renderer.invalidate_biome_cache()
        self.camera.set_world(self.world)

    def _screen_to_world(self, sx: int, sy: int) -> tuple[float, float]:
        return float(sx + self.camera.x), float(sy + self.camera.y)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _save(self) -> None:
        try:
            self.doc.save(WORLD_REL_PATH)
            self._dirty = False
            self.status = f"保存しました ({WORLD_REL_PATH})"
            self._reload_world()
        except Exception as exc:
            self.status = f"保存失敗: {exc}"

    def _cycle_type(self, delta: int) -> None:
        options = self.doc.type_options(self.active_layer)
        if not options:
            return
        self.type_index = (self.type_index + delta) % len(options)

    def _delete_selected(self) -> None:
        if self.selected_uid is None:
            return
        obj = next((o for o in self.doc.objects if o.uid == self.selected_uid), None)
        if obj is None:
            return
        if obj.layer in SITE_LAYERS:
            self.status = "拠点は削除できません（移動のみ）"
            return
        self.doc.remove_object(self.selected_uid)
        self.selected_uid = None
        self._mark_dirty()
        self._reload_world()
        self.status = "削除しました"

    def _place_at(self, wx: float, wy: float) -> None:
        type_ref = self._current_type()
        obj = self.doc.add_object(self.active_layer, type_ref, wx, wy)
        self.selected_uid = obj.uid
        self._mark_dirty()
        self._reload_world()
        self.status = f"配置: {LAYER_LABELS[self.active_layer]} / {type_ref}"

    def _handle_mouse_down(self, button: int, pos: tuple[int, int]) -> None:
        wx, wy = self._screen_to_world(*pos)
        if button == 2 or (button == 1 and self._space_held):
            self._panning = True
            self._pan_last = pos
            return
        if button == 3:
            hit = self.doc.find_at(self.active_layer, wx, wy, all_layers=True)
            if hit and hit.layer not in SITE_LAYERS:
                self.doc.remove_object(hit.uid)
                if self.selected_uid == hit.uid:
                    self.selected_uid = None
                self._mark_dirty()
                self._reload_world()
                self.status = "削除しました"
            return
        if button != 1:
            return
        if pos[0] < HUD_LEFT or pos[1] < HUD_TOP:
            return

        hit = self.doc.find_at(self.active_layer, wx, wy, all_layers=True)
        if hit is not None:
            self.selected_uid = hit.uid
            self.active_layer = hit.layer
            options = self.doc.type_options(hit.layer)
            if hit.type_ref in options:
                self.type_index = options.index(hit.type_ref)
            self._dragging_uid = hit.uid
            return

        self._place_at(wx, wy)

    def _handle_mouse_up(self, button: int) -> None:
        if button in (1, 2):
            self._panning = False
            if self._dragging_uid is not None:
                self._reload_world()
            self._dragging_uid = None

    def _handle_mouse_motion(self, pos: tuple[int, int], buttons: tuple[int, ...]) -> None:
        if self._panning:
            dx = pos[0] - self._pan_last[0]
            dy = pos[1] - self._pan_last[1]
            self.camera.x -= dx
            self.camera.y -= dy
            self.camera._clamp_position()
            self._pan_last = pos
            return

        if self._dragging_uid and buttons[0]:
            wx, wy = self._screen_to_world(*pos)
            obj = next((o for o in self.doc.objects if o.uid == self._dragging_uid), None)
            if obj is not None:
                if obj.layer in SITE_LAYERS:
                    self.doc.move_site_with_access(obj, wx, wy)
                else:
                    obj.x = wx
                    obj.y = wy
                self._mark_dirty()

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._space_held = True
            return
        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._space_held = False
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key in LAYER_KEYS:
            self.active_layer = LAYER_KEYS[event.key]
            self.type_index = 0
            return
        if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
            self._cycle_type(-1 if event.key == pygame.K_LEFTBRACKET else 1)
            return
        if event.key == pygame.K_DELETE:
            self._delete_selected()
            return
        if event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            self._save()
            return
        if event.key == pygame.K_ESCAPE:
            self.selected_uid = None
            return

    def _draw_hud(self) -> None:
        panel = pygame.Surface((HUD_LEFT, self.screen_h), pygame.SRCALPHA)
        panel.fill((12, 18, 12, 230))
        self.screen.blit(panel, (0, 0))

        top = pygame.Surface((self.screen_w, HUD_TOP), pygame.SRCALPHA)
        top.fill((12, 18, 12, 210))
        self.screen.blit(top, (0, 0))

        y = 12
        title = "マップエディタ Phase 1"
        dirty = " *" if self._dirty else ""
        self.screen.blit(self.big_font.render(title + dirty, True, (220, 235, 200)), (12, y))
        y += 36
        self.screen.blit(self.small_font.render(self.status, True, (180, 200, 170)), (12, y))
        y += 28

        self.screen.blit(self.font.render("レイヤー (1-4):", True, (200, 210, 180)), (12, y))
        y += 26
        for i, layer in enumerate(LAYER_ORDER, start=1):
            mark = ">" if layer == self.active_layer else " "
            count = len(self.doc.objects_in_layer(layer))
            line = f"{mark} {i}. {LAYER_LABELS[layer]} ({count})"
            color = (255, 230, 120) if layer == self.active_layer else (160, 170, 150)
            self.screen.blit(self.font.render(line, True, color), (20, y))
            y += 24

        y += 8
        self.screen.blit(self.font.render("配置タイプ [ ]:", True, (200, 210, 180)), (12, y))
        y += 24
        type_ref = self._current_type()
        self.screen.blit(self.font.render(f"  {type_ref}", True, (255, 240, 160)), (12, y))
        y += 32

        if self.selected_uid:
            obj = next((o for o in self.doc.objects if o.uid == self.selected_uid), None)
            if obj:
                self.screen.blit(self.font.render("選択中:", True, (200, 210, 180)), (12, y))
                y += 24
                for line in (
                    f"  {obj.layer} / {obj.type_ref}",
                    f"  x={obj.x:.1f} y={obj.y:.1f}",
                    f"  r≈{self.doc.resolve_radius(obj):.0f}",
                ):
                    self.screen.blit(self.small_font.render(line, True, (190, 200, 170)), (12, y))
                    y += 20

        y = self.screen_h - 120
        help_lines = [
            "左クリック: 配置/選択",
            "ドラッグ: 移動",
            "右クリック: 削除",
            "中クリック/Space+左: パン",
            "Ctrl+S: 保存",
        ]
        for line in help_lines:
            self.screen.blit(self.small_font.render(line, True, (140, 150, 130)), (12, y))
            y += 18

    def _draw_selection(self) -> None:
        if not self.selected_uid:
            return
        obj = next((o for o in self.doc.objects if o.uid == self.selected_uid), None)
        if obj is None:
            return
        sx = int(obj.x - self.camera.x)
        sy = int(obj.y - self.camera.y)
        rect = self.doc.rect_half_extents(obj)
        if rect is not None:
            hw, hh = int(rect[0]) + 3, int(rect[1]) + 3
            pygame.draw.rect(
                self.screen,
                (255, 255, 100),
                pygame.Rect(sx - hw, sy - hh, hw * 2, hh * 2),
                2,
            )
            return
        radius = int(self.doc.resolve_radius(obj)) + 4
        pygame.draw.circle(self.screen, (255, 255, 80), (sx, sy), radius, 2)

    def _draw_nest_markers(self) -> None:
        for obj in self.doc.objects_in_layer("colony_site"):
            sx = int(obj.x - self.camera.x)
            sy = int(obj.y - self.camera.y)
            colony_id = self.doc.colony_id_for_site(obj)
            style = get_faction_style(self.world, colony_id)
            outer = style.get("nest_outer", (90, 45, 30))
            inner = style.get("nest_inner_base", (180, 90, 40))
            tr = min(36, int(self.doc.resolve_radius(obj) * 0.2))
            pygame.draw.circle(self.screen, outer, (sx, sy), tr + 4, 2)
            pygame.draw.circle(self.screen, inner, (sx, sy), tr)
            label = style.get("label", colony_id[:1])
            self.screen.blit(self.small_font.render(str(label), True, (255, 240, 220)), (sx - 6, sy - 8))
        for obj in self.doc.objects_in_layer("colony_access"):
            sx = int(obj.x - self.camera.x)
            sy = int(obj.y - self.camera.y)
            pygame.draw.circle(self.screen, (200, 160, 80), (sx, sy), 6, 2)

    def _draw_frame(self) -> None:
        self.renderer.screen = self.screen
        self.screen.fill(self.renderer.UI_MARGIN_COLOR)
        self.renderer._draw_background(self.world, self.camera, map_view_mode="biome")

        clip = pygame.Rect(HUD_LEFT, HUD_TOP, self.screen_w - HUD_LEFT, self.screen_h - HUD_TOP)
        self.screen.set_clip(clip)
        ObstacleRenderer.draw(self.world, self.screen, self.camera)
        ZoneRenderer.draw(self.world, self.screen, self.camera)
        SpawnEmitterRenderer.draw(self.world, self.screen, self.camera)
        self._draw_nest_markers()
        self._draw_selection()

        # ワールド境界
        cam_x, cam_y = int(self.camera.x), int(self.camera.y)
        border = pygame.Rect(-cam_x, -cam_y, self.world.width, self.world.height)
        pygame.draw.rect(self.screen, (90, 110, 80), border, 2)
        self.screen.set_clip(None)

        self._draw_hud()

    def run(self) -> None:
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen_w, self.screen_h = event.size
                    self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
                    self.camera.set_screen_size(self.screen_w, self.screen_h)
                    self.camera.set_pan_insets(top=HUD_TOP, left=HUD_LEFT)
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event)
                elif event.type == pygame.KEYUP:
                    self._handle_key(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_down(event.button, event.pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._handle_mouse_up(event.button)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event.pos, event.buttons)

            self._draw_frame()
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


def main() -> None:
    MapEditorApp().run()


if __name__ == "__main__":
    main()
