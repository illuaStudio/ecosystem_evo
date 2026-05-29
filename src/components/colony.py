# colony.py
"""コロニー（巣）所属と獲物運搬の状態。"""


class ColonyComponent:
    def __init__(self, nest_id: int | None = None, colony_id: str | None = None):
        self.nest_id = nest_id
        self.colony_id = colony_id
        self.defeated = False
        self.carried_biomass = 0.0
        self.carried_carcass = None

    @property
    def is_carrying(self) -> bool:
        return self.carried_biomass > 0
