# colony.py
"""コロニー（巣）所属と獲物運搬の状態。"""


class ColonyComponent:
    def __init__(self, nest_id: int | None = None):
        self.nest_id = nest_id
        self.carried_carcass = None

    @property
    def is_carrying(self) -> bool:
        carcass = self.carried_carcass
        return carcass is not None and not getattr(carcass, "alive", True)
