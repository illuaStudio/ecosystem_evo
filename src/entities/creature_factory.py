# creature_factory.py
import random

from src.entities.creature import Creature


class CreatureFactory:
    """生物生成専用ファクトリー
    Worldを必ず渡す設計にすることで依存関係を明確化
    """

    @staticmethod
    def create(species_name: str = "Amoeba", world=None, x: float = None, y: float = None):
        """Worldを必須で受け取る"""
        if world is None:
            raise ValueError("CreatureFactory.create() には 'world' 引数が必須です。")

        # Worldの範囲内でランダム生成
        margin = 80
        if x is None:
            x = random.randint(margin, int(world.width) - margin)
        if y is None:
            y = random.randint(margin, int(world.height) - margin)

        creature = Creature(x, y, species_name)
        creature.world = world  # World参照を設定

        return creature

    @staticmethod
    def create_offspring(
        parent,
        x: float,
        y: float,
        *,
        base_size: float,
        satiety: float,
        age: int = 0,
    ):
        """親個体から子を生成（無性分裂・将来的な卵生/有性生殖の共通入口）。"""
        if parent.world is None:
            raise ValueError("create_offspring() には親の world 参照が必要です。")

        child = Creature(x, y, parent.species.name)
        child.world = parent.world
        child.traits["base_size"] = float(base_size)
        child.satiety = max(0.0, min(child.max_satiety, float(satiety)))
        child.age = age
        return child
