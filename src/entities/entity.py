class BaseEntity:
    """全てのエンティティ（草、蟻、将来的に食虫植物など）の基底クラス"""

    def __init__(self, x: float, y: float):
        self.pos = [x, y]
        self.last_pos = [x, y]
        self.age = 0
        self.alive = True

    def update(self, *args, **kwargs):
        """サブクラスでオーバーライド"""
        pass

    def draw(self, screen, camera):
        """サブクラスでオーバーライド"""
        pass

    def is_dead(self) -> bool:
        return not self.alive

    def kill(self):
        self.alive = False
