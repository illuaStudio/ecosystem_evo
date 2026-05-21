# world.py
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from config import config
from creature_factory import CreatureFactory


class World:
    """ゲーム世界全体を管理。設定は config/worlds/*.json から読み込む。

    Grassland.json の例:
        {
          "name": "Grassland",
          "display_name": "草原の生態系",
          "world_width": 800,
          "world_height": 600,
          "background_color": [34, 60, 25],
          "mana": { "initial": 4500.0, "max": 12000.0, "regen_rate": 0.8 },
          "initial_entities": { "Amoeba": 25, "Predator": 6 },
          "environment": { "temperature": 22.0, "humidity": 65.0 }
        }

    初期化:
        world = World("Grassland")           # config から name で取得
        world = World.from_json(path_or_dict)  # ファイルまたは dict から直接
    """

    def __init__(self, world_name: str = "Grassland"):
        world_data = config.get_world(world_name)
        if not world_data:
            world_data = self._load_world_file(world_name)
        if not world_data:
            raise ValueError(
                f"ワールド '{world_name}' が見つかりません。"
                f" config/worlds/*.json を確認してください。"
            )
        self._init_from_data(world_data)

    @staticmethod
    def _load_world_file(world_name: str) -> Optional[Dict]:
        """config キャッシュに無い場合のフォールバック読み込み"""
        worlds_dir = config.base_path / "worlds"
        for candidate in (
            worlds_dir / f"{world_name}.json",
            worlds_dir / f"{world_name.lower()}.json",
        ):
            if candidate.exists():
                with open(candidate, encoding="utf-8") as f:
                    return json.load(f)
        return None

    @classmethod
    def from_json(cls, source: Union[str, Path, Dict]) -> "World":
        """JSON ファイルパスまたは辞書から World を構築する。"""
        if isinstance(source, dict):
            world = cls.__new__(cls)
            world._init_from_data(source)
            return world

        path = Path(source)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_json(data)

    def _init_from_data(self, world_data: Dict) -> None:
        self.name = world_data["name"]
        self.display_name = world_data.get("display_name", self.name)
        self.width = int(world_data["world_width"])
        self.height = int(world_data["world_height"])
        self.background_color = tuple(world_data.get("background_color", [34, 60, 25]))

        mana_cfg = world_data.get("mana", {})
        self.mana = float(mana_cfg.get("initial", 5000.0))
        self.max_mana = float(mana_cfg.get("max", self.mana))
        self.mana_regen_rate = float(mana_cfg.get("regen_rate", 0.0))
        self.mana = min(self.mana, self.max_mana)

        env = world_data.get("environment", {})
        self.temperature = float(env.get("temperature", 20.0))
        self.humidity = float(env.get("humidity", 50.0))

        self.creatures: List = []
        self.obstacles = []
        self.resources = []

        self._spawn_initial_entities(world_data)

    def _spawn_initial_entities(self, world_data: Dict) -> None:
        """initial_entities に従って生物を配置（旧 initial_amoeba 等も互換）。"""
        initial = dict(world_data.get("initial_entities", {}))

        if not initial:
            if world_data.get("initial_amoeba"):
                initial["Amoeba"] = world_data["initial_amoeba"]
            if world_data.get("initial_predator"):
                initial["Predator"] = world_data["initial_predator"]

        factory = CreatureFactory()
        for species_name, count in initial.items():
            n = int(count)
            if n <= 0:
                continue
            if species_name not in config.species:
                print(f"警告: 種族 '{species_name}' の JSON が無いためスキップします")
                continue
            for _ in range(n):
                self.add_creature(factory.create(species_name, world=self))

    def add_creature(self, creature) -> None:
        """生物を世界に追加"""
        creature.world = self
        self.creatures.append(creature)

    def remove_creature(self, creature) -> None:
        if creature in self.creatures:
            self.creatures.remove(creature)

    def return_mana_from_decomposition(self, amount: float) -> None:
        """死骸の自然分解・捕食残りからのマナ還元（上限 max_mana）。"""
        if amount > 0:
            self.mana = min(self.max_mana, self.mana + amount)

    def consume_mana(self, amount: float) -> float:
        """マナ吸収などで消費。実際に減らせた量を返す。"""
        if amount <= 0 or self.mana <= 0:
            return 0.0
        taken = min(amount, self.mana)
        self.mana -= taken
        return taken

    def update(self) -> None:
        """全生物更新とマナの自然回復"""
        if self.mana_regen_rate > 0 and self.mana < self.max_mana:
            self.mana = min(self.max_mana, self.mana + self.mana_regen_rate)

        for creature in self.creatures[:]:
            creature.update()
            if creature.is_dead():
                self.remove_creature(creature)

    def get_nearest_creature(
        self,
        pos: Tuple[float, float],
        species_name: str = None,
        max_dist: float = 9999.0,
        exclude=None,
    ):
        """最も近い対象を探す"""
        best = None
        min_dist = float("inf")

        for c in self.creatures:
            if c is exclude or not getattr(c, "alive", True):
                continue
            if species_name and c.species.name != species_name:
                continue
            dist = math.hypot(c.pos[0] - pos[0], c.pos[1] - pos[1])
            if dist < min_dist and dist <= max_dist:
                min_dist = dist
                best = c
        return best

    def is_valid_position(self, x: float, y: float) -> bool:
        return 30 <= x <= self.width - 30 and 30 <= y <= self.height - 30
