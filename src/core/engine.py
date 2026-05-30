# engine.py
import pygame

from src.config import config
from src.core.camera import Camera
from src.core.input_handler import InputHandler
from src.core.species_visibility import SpeciesVisibilityManager
from src.entities.creature_factory import CreatureFactory
from src.rendering.renderer import Renderer
from src.sim.events import (
    ColonyDefeatedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SimEvent,
    SpawnEvent,
)
from src.systems.world import World


class SimulationEngine:
    """メインエンジン"""

    def __init__(self):
        # 画面サイズ（config.gameから取得）。RESIZABLE で最大化・端ドラッグを有効化
        self._window_flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(
            (config.game["camera_width"], config.game["camera_height"]),
            self._window_flags,
        )
        pygame.display.set_caption(
            f"{config.game['game_title']} v{config.game['version']}"
        )

        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.creature_factory = CreatureFactory()

        self.world = None
        self.paused = False
        self.sim_ticks_per_step = max(1, int(config.game.get("sim_ticks_per_step", 10)))
        self._render_ticks_until_sim = 0
        self.selected_creature = None
        self.selected_nest = None
        self.show_debug = config.game.get("debug_mode", False)
        self.map_view_mode = "biome"  # "biome" | "mana"
        self.show_territory = False
        self.user_message = ""
        self.species_visibility = SpeciesVisibilityManager()

        # レンダラーとインプットハンドラ
        font_size = config.game.get("ui_font_size", 24)
        self.renderer = Renderer(
            self.screen,
            pygame.font.SysFont("msgothic", font_size),
            pygame.font.SysFont("msgothic", font_size - 6),
            pygame.font.SysFont("msgothic", font_size + 8)
        )

        self.input_handler = InputHandler(self)

        self.reset_simulation()

    def resize_display(self, width: int, height: int) -> None:
        """ウィンドウリサイズ・最大化時に描画面とカメラを更新する。"""
        width = max(320, int(width))
        height = max(240, int(height))
        self.screen = pygame.display.set_mode((width, height), self._window_flags)
        self.renderer.screen = self.screen
        self.renderer._ui_panel = None
        self.camera.set_screen_size(width, height)

    def reset_simulation(self, world_name: str = "Grassland"):
        """シミュレーション初期化"""
        config.reload_all()
        pygame.display.set_caption(
            f"{config.game['game_title']} v{config.game['version']}"
        )
        self.sim_ticks_per_step = max(1, int(config.game.get("sim_ticks_per_step", 10)))
        self._render_ticks_until_sim = 0
        self.show_debug = config.game.get("debug_mode", False)
        self.world = World(world_name)
        self.selected_creature = None
        self.selected_nest = None
        self.species_visibility.reset_for_world(self.world)
        self.renderer.invalidate_biome_cache()

        # カメラにWorld情報を渡す（重要）
        self.camera.set_world(self.world)

        print(f"ワールド「{self.world.display_name}」をロードしました: {len(self.world.creatures)}匹")
        if self.show_debug:
            pending = len(self.world.events.drain())
            if pending:
                print(f"  [sim] 初期配置イベント {pending} 件（debug_mode で破棄）")
        if self.world.biome.biome_noise:
            bn = self.world.biome.biome_noise
            print(
                f"  biome_noise: scale={bn.scale}, octaves={bn.octaves}, "
                f"threshold={bn.threshold}, seed={bn.seed}"
            )

    def handle_events(self) -> bool:
        """入力処理をInputHandlerに委譲"""
        return self.input_handler.handle_events()

    def _sim_dt(self) -> float:
        """1 回のシミュ更新で進むシミュレーション時間（レンダー tick 換算）。"""
        speed = float(config.game.get("simulation_speed", 1.0))
        return self.sim_ticks_per_step * speed

    def _log_sim_event(self, event: SimEvent) -> None:
        name = type(event).__name__
        if isinstance(event, SpawnEvent):
            print(
                f"[sim] {name} {event.species_name} source={event.source}",
                flush=True,
            )
        elif isinstance(event, DeathEvent):
            print(
                f"[sim] {name} {event.species_name} cause={event.cause}",
                flush=True,
            )
        elif isinstance(event, ItemFoundEvent):
            print(
                f"[sim] {name} {event.species_name} amount={event.amount:.1f}",
                flush=True,
            )
        elif isinstance(event, CombatStartedEvent):
            target = event.target_creature
            target_name = (
                target.species.name if target is not None else event.target_colony_id
            )
            print(
                f"[sim] {name} {event.attacker_species} -> {target_name}",
                flush=True,
            )
        elif isinstance(event, ColonyDefeatedEvent):
            print(f"[sim] {name} {event.colony_id}", flush=True)
        else:
            print(f"[sim] {name}", flush=True)

    def update(self):
        """状態更新（レンダー tick）。生態シミュは sim_ticks_per_step ごとに実行。"""
        if self.paused or self.world is None:
            return
        if self._render_ticks_until_sim > 0:
            self._render_ticks_until_sim -= 1
            return
        self.world.update(self._sim_dt())
        for event in self.world.events.drain():
            if self.show_debug:
                self._log_sim_event(event)
            if isinstance(event, ColonyDefeatedEvent):
                self.user_message = event.message
        self._render_ticks_until_sim = self.sim_ticks_per_step - 1

    def _update_camera_pan_insets(self) -> None:
        """HUD の大きさに合わせ、マップ端を UI の下までずらせるパン余白を設定する。"""
        extra = float(config.game.get("camera_pan_extra", 16))
        has_selection = (
            self.selected_creature is not None or self.selected_nest is not None
        )
        sw = self.screen.get_width()
        top = (
            Renderer.HUD_TOP_HEIGHT_DEBUG
            if self.show_debug
            else Renderer.HUD_TOP_HEIGHT
        ) + extra
        left = (min(Renderer.HUD_LEFT_PANEL_WIDTH, sw) if has_selection else 0) + extra
        right = max(
            Renderer.HUD_RIGHT_PANEL_WIDTH,
            Renderer.HUD_VISIBILITY_PANEL_WIDTH,
        ) + extra
        bottom = extra
        self.camera.set_pan_insets(top=top, left=left, right=right, bottom=bottom)

    def clear_selection_if_creature_hidden(self) -> None:
        from src.shelter.state import is_creature_sheltered

        sc = self.selected_creature
        if sc is None:
            return
        if is_creature_sheltered(sc):
            self.selected_creature = None
            return
        if not self.species_visibility.is_creature_visible(sc):
            self.selected_creature = None

    def draw(self):
        """描画"""
        self.clear_selection_if_creature_hidden()
        self._update_camera_pan_insets()
        self.renderer.draw(
            self.world.creatures,
            self.camera,
            self.selected_creature,
            self.selected_nest,
            self.paused,
            self.show_debug,
            self.map_view_mode,
            self.show_territory,
            user_message=getattr(self, "user_message", ""),
            species_visibility=self.species_visibility,
        )

    def run(self):
        """メインループ"""
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(config.game["fps"])
