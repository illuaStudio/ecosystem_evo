from config import config

# 身体的・基礎特性のみ（アクション固有値は mind.actions[].params へ）
ESSENTIAL_TRAIT_KEYS = frozenset({
    "base_size",
    "base_speed",
    "base_vision",
    "max_hp",
    "max_satiety",
    "metabolism_rate",
})

TRAIT_DEFAULTS = {
    "base_size": 9.0,
    "base_speed": 1.0,
    "base_vision": 120.0,
    "max_hp": 100.0,
    "max_satiety": 80.0,
    "metabolism_rate": 0.5,
}

# Amoeba JSON 例（traits は最小、mana_absorption_rate は Action.params 側）:
# {
#   "traits": {
#     "base_size": 9.0, "base_speed": 1.8, "base_vision": 140,
#     "max_hp": 60.0, "max_satiety": 45.0, "metabolism_rate": 0.55
#   },
#   "mind": {
#     "actions": [{
#       "name": "ManaWanderAction",
#       "params": {
#         "angle_range": 40,
#         "speed_multiplier": 0.75,
#         "mana_absorption_rate": 0.8
#       }
#     }]
#   }
# }


def normalize_traits(raw: dict) -> dict:
    """JSON の traits を身体特性のみに正規化し、欠損キーにデフォルトを補う。"""
    traits = {k: raw[k] for k in ESSENTIAL_TRAIT_KEYS if k in raw}
    for key, default in TRAIT_DEFAULTS.items():
        traits.setdefault(key, default)
    return traits


class Species:
    @classmethod
    def create(cls, name: str = "Amoeba"):
        data = config.get_species(name)
        return cls(data)

    def __init__(self, data: dict):
        self.name = data["name"]
        self.color = tuple(data.get("color", [120, 200, 120]))
        self.traits = normalize_traits(data.get("traits", {}))
        self.mind_data = data.get("mind", {"type": "priority", "actions": []})
        self.description = data.get("description", "")
