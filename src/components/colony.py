# colony.py
"""コロニー（巣）所属と獲物運搬の状態。"""


class ColonyComponent:
    def __init__(self, nest_id: int | None = None):
        self.nest_id = nest_id
        self.carried_biomass = 0.0
        self.carried_carcass = None

    @property
    def is_carrying(self) -> bool:
        return self.carried_biomass > 0
