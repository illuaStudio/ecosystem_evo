# engine.py
import pygame
from world import World
from camera import Camera
from renderer import Renderer
from input_handler import InputHandler
from creature_factory import CreatureFactory
from config import config


class SimulationEngine:
    """メインエンジン"""
    
    def __init__(self):
        # 画面サイズ（config.gameから取得）
        self.screen = pygame.display.set_mode((
            config.game["camera_width"],
            config.game["camera_height"]
        ))
        pygame.display.set_caption(
            f"{config.game['game_title']} v{config.game['version']}"
        )

        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.creature_factory = CreatureFactory()

        self.world = None
        self.paused = False
        self.selected_creature = None
        self.show_debug = config.game.get("debug_mode", False)

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

    def reset_simulation(self, world_name: str = "Grassland"):
        """シミュレーション初期化"""
        config.reload_worlds()
        self.world = World(world_name)
        self.selected_creature = None
        self.renderer.invalidate_biome_cache()

        # カメラにWorld情報を渡す（重要）
        self.camera.set_world(self.world)

        print(f"ワールド「{self.world.display_name}」をロードしました: {len(self.world.creatures)}匹")
        if self.world.biome_noise:
            bn = self.world.biome_noise
            print(
                f"  biome_noise: scale={bn.scale}, octaves={bn.octaves}, "
                f"threshold={bn.threshold}, seed={bn.seed}"
            )

    def handle_events(self) -> bool:
        """入力処理をInputHandlerに委譲"""
        return self.input_handler.handle_events()

    def update(self):
        """状態更新"""
        if self.paused:
            return
        self.world.update()

    def draw(self):
        """描画"""
        self.renderer.draw(
            self.world.creatures,
            self.camera,
            self.selected_creature,
            self.paused,
            self.show_debug
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