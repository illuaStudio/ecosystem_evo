# colony.py
"""コロニー（巣）所属の状態。持ち物は InventoryComponent が管理する。"""


class ColonyComponent:
    def __init__(self, nest_id: int | None = None, colony_id: str | None = None):
        self.nest_id = nest_id
        self.colony_id = colony_id
        self.defeated = False
