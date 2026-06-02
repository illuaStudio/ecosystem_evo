"""pygame クライアント: 描画・入力・SimRunner / GameController の統合。"""
import pygame

from src.config import config
from src.client.camera import Camera
from src.client.game_message_feed import GameMessageFeed
from src.client.input_handler import InputHandler
from src.client.rendering.renderer import Renderer
from src.client.species_visibility import SpeciesVisibilityManager
from src.game import client_api
from src.game.game_controller import GameController
from src.game.sim_runner import SimRunner
from src.sim.bridge import SimBridge
from src.sim.systems.world import World


def colony(world):
    """Client から Game の colony データにアクセスする際は必ず client_api 経由。
    異なるAI (Client担当 / Game担当) が並行開発できるための境界。
    """
    return client_api.try_get_colony_orchestrator(world)


class GameApp:
    """Client 層メインループ（Sim + Game + Presentation）。"""

    def __init__(self):
        self._window_flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(
            (config.client["camera_width"], config.client["camera_height"]),
            self._window_flags,
        )
        pygame.display.set_caption(
            f"{config.game_app['game_title']} v{config.game_app['version']}"
        )

        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.sim_runner = SimRunner()
        self.world = None
        self.paused = False
        self.selected_creature = None
        self.selected_affiliation_id: str | None = None
        self.show_debug = config.client.get("debug_hud", False)
        self.debug_game_messages = config.client.get("debug_game_messages", False)
        self.map_view_mode = "biome"
        self.show_territory = False
        self.show_sheltered = False
        self.user_message = ""
        self.message_feed = GameMessageFeed()
        self.game_controller = GameController()
        self.sim_bridge: SimBridge | None = None
        self.species_visibility = SpeciesVisibilityManager()

        font_size = config.client.get("ui_font_size", 24)
        self.renderer = Renderer(
            self.screen,
            pygame.font.SysFont("msgothic", font_size),
            pygame.font.SysFont("msgothic", font_size - 6),
            pygame.font.SysFont("msgothic", font_size + 8),
        )
        self.input_handler = InputHandler(self)
        self.reset_simulation()

    def resize_display(self, width: int, height: int) -> None:
        width = max(320, int(width))
        height = max(240, int(height))
        self.screen = pygame.display.set_mode((width, height), self._window_flags)
        self.renderer.screen = self.screen
        self.renderer._ui_panel = None
        self.camera.set_screen_size(width, height)

    def reset_simulation(self, world_name: str = "Grassland"):
        config.reload_all()
        pygame.display.set_caption(
            f"{config.game_app['game_title']} v{config.game_app['version']}"
        )
        self.sim_runner.reload()
        self.show_debug = config.client.get("debug_hud", False)
        self.debug_game_messages = config.client.get("debug_game_messages", False)
        debug_sim = config.client.get("debug_sim_events", False) or config.sim.get(
            "debug_events", False
        )
        self.world = World(world_name)
        from src.game.sim_bridge_factory import make_sim_bridge

        self.sim_bridge = make_sim_bridge(self.world)
        self.game_controller = GameController(bridge=self.sim_bridge)
        self.game_controller.debug_sim_events = debug_sim
        self.selected_creature = None
        self.selected_affiliation_id: str | None = None
        self.user_message = ""
        self.message_feed.clear()
        self.species_visibility.reset_for_world(self.world)
        self.renderer.invalidate_biome_cache()
        self.camera.set_world(self.world)
        self.game_controller.reset_for_world(self.world, bridge=self.sim_bridge)

        print(
            f"ワールド「{self.world.display_name}」をロードしました: "
            f"{len(self.world.creatures)}匹"
        )
        if self.show_debug:
            print(
                f"  [game] プレイヤー勢力: {self.game_controller.state.player_affiliation_id}"
            )
        if self.world.biome.biome_noise:
            bn = self.world.biome.biome_noise
            print(
                f"  biome_noise: scale={bn.scale}, octaves={bn.octaves}, "
                f"threshold={bn.threshold}, seed={bn.seed}"
            )

    def handle_events(self) -> bool:
        return self.input_handler.handle_events()

    def debug_spawn_creature(self, species: str) -> None:
        """デバッグキー用: Bridge 経由スポーン（ランダム座標）。"""
        if self.game_controller.bridge is None:
            return
        self.game_controller.spawn_creature(species, source="debug")

    def debug_spawn_affiliation_member(self, species: str = "red_ant") -> None:
        """巣付近へコロニー種をスポーン。"""
        if self.world is None or self.game_controller.bridge is None:
            return
        from src.config import config

        affiliation_cfg = (config.get_species(species) or {}).get("affiliation", {})
        if affiliation_cfg.get("enabled"):
            x, y = colony(self.world).spawn_position(species, affiliation_cfg)
            self.game_controller.spawn_creature(species, x=x, y=y, source="debug")
        else:
            self.game_controller.spawn_creature(species, source="debug")

    def notify(self, text: str, *, source: str = "game", priority: int = 0) -> None:
        """画面上のメッセージ欄へ通知。"""
        if not text:
            return
        self.message_feed.push_text(text, source=source, priority=priority)
        self.user_message = text

    def update(self):
        if self.paused or self.world is None:
            return
        if not self.sim_runner.should_run_sim_tick():
            return
        if not client_api.should_advance_sim(self.game_controller):
            tick_messages = self.game_controller.on_tick(self.world)
            self.message_feed.push(tick_messages)
            if self.debug_game_messages or self.show_debug:
                for msg in tick_messages:
                    print(f"[game:{msg.source}] {msg.text}", flush=True)
            if self.game_controller.user_message:
                self.user_message = self.game_controller.user_message
            return
        self.sim_runner.tick(self.world)
        tick_messages = self.game_controller.on_tick(self.world)
        self.message_feed.push(tick_messages)
        if self.debug_game_messages or self.show_debug:
            for msg in tick_messages:
                print(f"[game:{msg.source}] {msg.text}", flush=True)
        if self.game_controller.user_message:
            self.user_message = self.game_controller.user_message

    def _update_camera_pan_insets(self) -> None:
        extra = float(config.client.get("camera_pan_extra", 16))
        has_selection = (
            self.selected_creature is not None or self.selected_affiliation_id is not None
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
        from src.sim.shelter.state import is_creature_sheltered

        sc = self.selected_creature
        if sc is None:
            return
        if is_creature_sheltered(sc) and not self.show_sheltered:
            self.selected_creature = None
            return
        if not self.species_visibility.is_creature_visible(sc):
            self.selected_creature = None

    def draw(self):
        self.clear_selection_if_creature_hidden()
        self._update_camera_pan_insets()

        # Game層提供のシミュ時間・速度をHUD表示用に取得
        sim_time = 0.0
        sim_speed = 1.0
        if self.world is not None:
            sim_time = client_api.get_sim_time_seconds(self.world)
        if self.sim_runner is not None:
            sim_speed = client_api.get_simulation_speed(self.sim_runner)

        self.renderer.draw(
            self.world.creatures,
            self.camera,
            self.selected_creature,
            self.selected_affiliation_id,
            self.paused,
            self.show_debug,
            self.map_view_mode,
            self.show_territory,
            self.show_sheltered,
            user_message=getattr(self, "user_message", ""),
            message_feed=getattr(self, "message_feed", None),
            player_affiliation_id=self.game_controller.state.player_affiliation_id,
            game_state=self.game_controller.state,
            species_visibility=self.species_visibility,
            sim_time=sim_time,
            sim_speed=sim_speed,
        )

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(config.client["fps"])
