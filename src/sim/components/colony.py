# colony.py
"""コロニー所属の状態。持ち物は InventoryComponent が管理する。"""


class ColonyComponent:
    def __init__(self, colony_id: str | None = None):
        self.colony_id = colony_id
        self.defeated = False
